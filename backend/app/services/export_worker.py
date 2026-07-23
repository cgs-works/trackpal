"""Export worker — claims pending ExportJobs, builds ZIP, uploads to R2."""

from __future__ import annotations

import asyncio
import csv
import io
import json
import logging
import zipfile
from datetime import datetime, timezone

from app.core.database import AsyncSessionLocal
from app.models.export_job import ExportJob
from app.models.tenant import Tenant
from app.repositories import export_jobs_repository, tenants_repository
from app.services.export_service import get_storage
from app.services.export_storage import generate_random_export_key

logger = logging.getLogger(__name__)

_POLL_INTERVAL_S = 5
_MAX_RETRIES = 3


# ── ZIP builders ───────────────────────────────────────────────


def _build_account_profile_csv(tenant: Tenant, locale: str, tz: str) -> str:
    """Build account-profile.csv content."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "account_name",
        "contact_email",
        "whatsapp_phone",
        "login_username",
        "current_plan",
        "preferred_language",
        "time_zone",
    ])
    writer.writerow([
        tenant.name or "",
        tenant.email or "",
        tenant.whatsapp_phone or "",
        tenant.owner.username if tenant.owner else "",
        tenant.plan or "",
        locale,
        tz,
    ])
    return output.getvalue()


def _build_json(tenant: Tenant, locale: str, tz: str) -> str:
    """Build trackpal-data.json content."""
    data = {
        "export_metadata": {
            "export_format_version": "1",
            "generated_at": datetime.now(timezone.utc).isoformat(),
        },
        "account_profile": {
            "account_name": tenant.name or "",
            "contact_email": tenant.email or "",
            "whatsapp_phone": tenant.whatsapp_phone or "",
            "login_username": tenant.owner.username if tenant.owner else "",
            "current_plan": tenant.plan or "",
            "preferred_language": locale,
            "time_zone": tz,
        },
    }
    return json.dumps(data, indent=2, ensure_ascii=False)


def _build_readme(locale: str) -> str:
    """Build localized README.txt content."""
    if locale.startswith("es"):
        return _README_ES
    return _README_EN


_README_EN = """TrackPal Tenant Data Export
=============================

This file contains a snapshot of your account profile as recorded at the
generation time shown in trackpal-data.json.

Files in this bundle:
  account-profile.csv  — Your account profile in CSV format (UTF-8 with BOM)
  trackpal-data.json   — Your account profile in JSON format (UTF-8)

Fields in account-profile.csv / trackpal-data.json:
  account_name         — The name of your business
  contact_email        — The contact email for your business
  whatsapp_phone       — The WhatsApp phone number linked to your account
  login_username       — Your login username
  current_plan         — Your current plan (starter or pro)
  preferred_language   — Your preferred language (en or es)
  time_zone             — Your configured time zone

Notes:
  - CSV files use UTF-8 with BOM for compatible spreadsheet opening.
  - CSV values that could be interpreted as formulas are prefixed with
    a tab character to prevent accidental execution.
  - JSON uses null for unset optional fields.
  - This is a point-in-time snapshot. Changes made after the export
    generation will appear in a later export.
  - No passwords, tokens, secrets, or internal identifiers are included.
  - Downloaded copies do not expire and become your responsibility.
"""

_README_ES = """Exportación de datos de TrackPal — Mi cuenta
=================================================

Este archivo contiene una instantánea de los datos de tu perfil de
cuenta registrados al momento de la generación indicada en
trackpal-data.json.

Archivos incluidos:
  account-profile.csv  — Perfil de tu cuenta en formato CSV (UTF-8 con BOM)
  trackpal-data.json   — Perfil de tu cuenta en formato JSON (UTF-8)

Campos en account-profile.csv / trackpal-data.json:
  account_name         — El nombre de tu negocio
  contact_email        — El correo de contacto de tu negocio
  whatsapp_phone       — El número de WhatsApp vinculado a tu cuenta
  login_username       — Tu nombre de usuario de inicio de sesión
  current_plan         — Tu plan actual (starter o pro)
  preferred_language   — Tu idioma preferido (en o es)
  time_zone             — Tu zona horaria configurada

Notas:
  - Los archivos CSV usan UTF-8 con BOM para apertura compatible en hojas
    de cálculo.
  - Los valores CSV que podrían interpretarse como fórmulas tienen un
    prefijo de tabulación para evitar ejecución accidental.
  - JSON usa null para campos opcionales no establecidos.
  - Esta es una instantánea puntual. Los cambios realizados después de la
    generación aparecerán en una exportación posterior.
  - No se incluyen contraseñas, tokens, secretos ni identificadores
    internos.
  - Las copias descargadas no expiran y son tu responsabilidad.
"""


async def _build_zip(tenant: Tenant, locale: str, tz: str) -> bytes:
    """Build the export ZIP for the given tenant."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        # account-profile.csv
        csv_content = _build_account_profile_csv(tenant, locale, tz)
        # Add BOM for UTF-8 CSV
        csv_bytes = b"\xef\xbb\xbf" + csv_content.encode("utf-8")
        zf.writestr("account-profile.csv", csv_bytes)

        # trackpal-data.json
        json_content = _build_json(tenant, locale, tz)
        zf.writestr("trackpal-data.json", json_content.encode("utf-8"))

        # README.txt
        readme_content = _build_readme(locale)
        zf.writestr("README.txt", readme_content.encode("utf-8"))

    return buffer.getvalue()


# ── Worker ─────────────────────────────────────────────────────


async def _process_job_with_session(
    db: AsyncSessionLocal,  # type: ignore[valid-type]
    job: ExportJob,
) -> None:
    """Process one export job with a given DB session.

    This is the core processing seam — testable without touching the
    real worker loop or database connection lifecycle.
    """
    try:
        # Fetch tenant with owner
        tenant = await tenants_repository.get(db, job.tenant_id)
        if tenant is None:
            logger.warning("Tenant %s not found for job %s", job.tenant_id, job.id)
            await export_jobs_repository.update_status(
                db, job.id, "failed",
                error_code="TENANT_NOT_FOUND",
            )
            return

        # Resolve locale and timezone
        from app.repositories import tenant_settings_repository
        locale = await tenant_settings_repository.resolve_locale(db, job.tenant_id)
        tz = await tenant_settings_repository.resolve_timezone(db, job.tenant_id)

        # Build ZIP
        zip_bytes = await _build_zip(tenant, locale, tz)

        # Upload to R2
        storage = get_storage()
        r2_key = generate_random_export_key()
        await storage.upload(r2_key, zip_bytes, content_type="application/zip")

        # Transition to ready
        now = datetime.now(timezone.utc)
        from app.services.export_service import EXPORT_TTL_HOURS
        await export_jobs_repository.update_status(
            db, job.id, "ready",
            r2_key=r2_key,
            artifact_size_bytes=len(zip_bytes),
            expires_at=now + __import__("datetime").timedelta(hours=EXPORT_TTL_HOURS),
            clear_lease=True,
        )

        logger.info(
            "Export job %s completed — key=%s size=%d",
            job.id, r2_key, len(zip_bytes),
        )

    except Exception:
        logger.exception("Export job %s failed", job.id)
        # Increment attempts via update
        await export_jobs_repository.update_status(
            db, job.id, "failed",
            error_code="GENERATION_ERROR",
        )


async def _process_job(job: ExportJob) -> None:
    """Process one export job — creates its own DB session."""
    async with AsyncSessionLocal() as db:
        await _process_job_with_session(db, job)


async def export_worker_loop() -> None:
    """Background task: poll for pending ExportJobs and process them."""
    logger.info("Starting export worker loop")

    while True:
        try:
            async with AsyncSessionLocal() as db:
                job = await export_jobs_repository.claim_pending(db)

            if job is None:
                await asyncio.sleep(_POLL_INTERVAL_S)
                continue

            await _process_job(job)

        except asyncio.CancelledError:
            logger.info("Export worker loop cancelled")
            break
        except Exception:
            logger.exception("Unhandled error in export worker loop")
            await asyncio.sleep(_POLL_INTERVAL_S)
