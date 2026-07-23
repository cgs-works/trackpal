"""Export worker — claims pending ExportJobs, builds ZIP, uploads to R2."""

from __future__ import annotations

import asyncio
import csv
import io
import json
import logging
import re
import zipfile
from collections.abc import Sequence
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from app.core.database import AsyncSessionLocal
from app.models.blocked_client import BlockedClient
from app.models.client import Client
from app.models.export_job import ExportJob
from app.models.tenant import Tenant
from app.repositories import (
    blocked_clients_repository,
    clients_repository,
    export_jobs_repository,
    tenants_repository,
)
from app.services.export_service import get_storage
from app.services.export_storage import generate_random_export_key

logger = logging.getLogger(__name__)

_POLL_INTERVAL_S = 5
_MAX_RETRIES = 3


# ── Helpers ────────────────────────────────────────────────────


def _digits_only(value: str | None) -> str:
    """Extract only digits from a phone value."""
    if not value:
        return ""
    return re.sub(r"\D", "", value)


def _format_timestamp(dt: datetime | None, tz_name: str) -> str:
    """Format a datetime as ISO 8601 with explicit offset in *tz_name*."""
    if dt is None:
        return ""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    target_tz = ZoneInfo(tz_name)
    local_dt = dt.astimezone(target_tz)
    return local_dt.isoformat()


def _neutralize_csv_value(value: str) -> str:
    """Neutralize formula-injection prefixes in CSV values.

    Prefix values that could be interpreted as spreadsheet formulas
    with a tab character.
    """
    if value and value[0] in ("=", "+", "-", "@", "\t", "\r", "\n", "|", "%"):
        return "\t" + value
    return value


def _account_status(is_active: bool) -> str:
    """Map client is_active to account_status string."""
    return "active" if is_active else "inactive"


# ── ZIP builders ───────────────────────────────────────────────


def _build_account_profile_csv(tenant: Tenant, locale: str, tz: str) -> str:
    """Build account-profile.csv content."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "account_name",
            "contact_email",
            "whatsapp_phone",
            "login_username",
            "current_plan",
            "preferred_language",
            "time_zone",
        ]
    )
    writer.writerow(
        [
            tenant.name or "",
            tenant.email or "",
            tenant.whatsapp_phone or "",
            tenant.owner.username if tenant.owner else "",
            tenant.plan or "",
            locale,
            tz,
        ]
    )
    return output.getvalue()


def _build_client_data_csv(clients: Sequence[Client], tz: str) -> str:
    """Build client-data.csv content.

    Clients are sorted by login_username.  Internal identifiers,
    passwords, and WhatsApp LIDs are never serialized.
    """
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "client_name",
            "login_username",
            "whatsapp_phone",
            "account_status",
            "registered_on",
            "last_updated_on",
        ]
    )
    sorted_clients = sorted(clients, key=lambda c: c.username or "")
    for c in sorted_clients:
        writer.writerow(
            [
                _neutralize_csv_value(c.full_name or ""),
                c.username or "",
                _digits_only(c.phone),
                _account_status(c.is_active),
                _format_timestamp(c.created_at, tz),
                _format_timestamp(c.updated_at, tz),
            ]
        )
    return output.getvalue()


def _build_blocked_phones_csv(blocks: Sequence[BlockedClient], tz: str) -> str:
    """Build blocked-phones.csv content.

    Only blocks that have a phone value are included — LID-only blocks
    are deliberately omitted.  Rows sorted by phone.
    """
    # Exclude LID-only blocks (no phone)
    phone_blocks = [b for b in blocks if b.phone]
    phone_blocks.sort(key=lambda b: b.phone or "")

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "phone",
            "blocked_at",
        ]
    )
    for b in phone_blocks:
        writer.writerow(
            [
                _digits_only(b.phone),
                _format_timestamp(b.created_at, tz),
            ]
        )
    return output.getvalue()


def _build_json(
    tenant: Tenant,
    locale: str,
    tz: str,
    *,
    clients: Sequence[Client] | None = None,
    blocked_phones: Sequence[BlockedClient] | None = None,
) -> str:
    """Build trackpal-data.json content."""
    # Build client records
    client_records = []
    if clients:
        for c in sorted(clients, key=lambda c: c.username or ""):
            client_records.append(
                {
                    "client_name": c.full_name or "",
                    "login_username": c.username or "",
                    "whatsapp_phone": _digits_only(c.phone) or None,
                    "account_status": _account_status(c.is_active),
                    "registered_on": _format_timestamp(c.created_at, tz) or None,
                    "last_updated_on": _format_timestamp(c.updated_at, tz) or None,
                }
            )

    # Build blocked-phone records (exclude LID-only)
    phone_block_records = []
    if blocked_phones:
        phone_blocks = [b for b in blocked_phones if b.phone]
        phone_blocks.sort(key=lambda b: b.phone or "")
        for b in phone_blocks:
            phone_block_records.append(
                {
                    "phone": _digits_only(b.phone),
                    "blocked_at": _format_timestamp(b.created_at, tz) or None,
                }
            )

    data = {
        "export_metadata": {
            "export_format_version": "1",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "record_counts": {
                "account_profile": 1,
                "client_accounts": len(client_records),
                "blocked_phone_list": len(phone_block_records),
            },
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
        "client_accounts": client_records,
        "blocked_phone_list": phone_block_records,
    }
    return json.dumps(data, indent=2, ensure_ascii=False)


def _build_readme(locale: str) -> str:
    """Build localized README.txt content."""
    if locale.startswith("es"):
        return _README_ES
    return _README_EN


_README_EN = """TrackPal Tenant Data Export
=============================

This file contains a snapshot of your account data as recorded at the
generation time shown in trackpal-data.json.

Files in this bundle:
  account-profile.csv  — Your account profile in CSV format (UTF-8 with BOM)
  client-data.csv      — Your client records in CSV format (UTF-8 with BOM)
  blocked-phones.csv   — Phone-based access control blocks in CSV format (UTF-8 with BOM)
  trackpal-data.json   — All data sections in JSON format (UTF-8)

Fields in account-profile.csv / account_profile in trackpal-data.json:
  account_name         — The name of your business
  contact_email        — The contact email for your business
  whatsapp_phone       — The WhatsApp phone number linked to your account
  login_username       — Your login username
  current_plan         — Your current plan (starter or pro)
  preferred_language   — Your preferred language (en or es)
  time_zone             — Your configured time zone

Fields in client-data.csv / client_accounts in trackpal-data.json:
  client_name          — The full name of the client
  login_username       — The client login username
  whatsapp_phone       — The WhatsApp phone number of the client
  account_status       — Whether the client is active or inactive
  registered_on        — When the client was registered (timezone of your account)
  last_updated_on      — When the client was last updated (timezone of your account)

Fields in blocked-phones.csv / blocked_phone_list in trackpal-data.json:
  phone                — The blocked phone number (digits only)
  blocked_at           — When the block was created (timezone of your account)

Notes:
  - CSV files use UTF-8 with BOM for compatible spreadsheet opening.
  - CSV values that could be interpreted as formulas are prefixed with
    a tab character to prevent accidental execution.
  - JSON uses null for unset optional fields.
  - Access control blocks that contain only a WhatsApp LID (no phone
    number) are deliberately omitted from both formats.
  - This is a point-in-time snapshot. Changes made after the export
    generation will appear in a later export.
  - No passwords, tokens, secrets, or internal identifiers are included.
  - Downloaded copies do not expire and become your responsibility.
"""

_README_ES = """Exportación de datos de TrackPal — Mi cuenta
=================================================

Este archivo contiene una instantánea de los datos de tu cuenta
registrados al momento de la generación indicada en
trackpal-data.json.

Archivos incluidos:
  account-profile.csv  — Perfil de tu cuenta en formato CSV (UTF-8 con BOM)
  client-data.csv      — Registros de clientes en formato CSV (UTF-8 con BOM)
  blocked-phones.csv   — Bloques de acceso por teléfono en formato CSV (UTF-8 con BOM)
  trackpal-data.json   — Todas las secciones de datos en formato JSON (UTF-8)

Campos en account-profile.csv / account_profile en trackpal-data.json:
  account_name         — El nombre de tu negocio
  contact_email        — El correo de contacto de tu negocio
  whatsapp_phone       — El número de WhatsApp vinculado a tu cuenta
  login_username       — Tu nombre de usuario de inicio de sesión
  current_plan         — Tu plan actual (starter o pro)
  preferred_language   — Tu idioma preferido (en o es)
  time_zone             — Tu zona horaria configurada

Campos en client-data.csv / client_accounts en trackpal-data.json:
  client_name          — El nombre completo del cliente
  login_username       — El nombre de usuario del cliente
  whatsapp_phone       — El número de WhatsApp del cliente
  account_status       — Si el cliente está activo o inactivo
  registered_on        — Cuándo se registró el cliente (zona horaria de tu cuenta)
  last_updated_on      — Cuándo se actualizó por última vez (zona horaria de tu cuenta)

Campos en blocked-phones.csv / blocked_phone_list en trackpal-data.json:
  phone                — El número de teléfono bloqueado (solo dígitos)
  blocked_at           — Cuándo se creó el bloqueo (zona horaria de tu cuenta)

Notas:
  - Los archivos CSV usan UTF-8 con BOM para apertura compatible en hojas
    de cálculo.
  - Los valores CSV que podrían interpretarse como fórmulas tienen un
    prefijo de tabulación para evitar ejecución accidental.
  - JSON usa null para campos opcionales no establecidos.
  - Los bloques de control de acceso que contienen solo un WhatsApp LID
    (sin número telefónico) se omiten deliberadamente de ambos formatos.
  - Esta es una instantánea puntual. Los cambios realizados después de la
    generación aparecerán en una exportación posterior.
  - No se incluyen contraseñas, tokens, secretos ni identificadores
    internos.
  - Las copias descargadas no expiran y son tu responsabilidad.
"""


async def _build_zip(
    tenant: Tenant,
    locale: str,
    tz: str,
    *,
    clients: Sequence[Client] | None = None,
    blocked_phones: Sequence[BlockedClient] | None = None,
) -> bytes:
    """Build the export ZIP for the given tenant."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        # account-profile.csv
        csv_content = _build_account_profile_csv(tenant, locale, tz)
        csv_bytes = b"\xef\xbb\xbf" + csv_content.encode("utf-8")
        zf.writestr("account-profile.csv", csv_bytes)

        # client-data.csv
        csv_content = _build_client_data_csv(clients or [], tz)
        csv_bytes = b"\xef\xbb\xbf" + csv_content.encode("utf-8")
        zf.writestr("client-data.csv", csv_bytes)

        # blocked-phones.csv
        csv_content = _build_blocked_phones_csv(blocked_phones or [], tz)
        csv_bytes = b"\xef\xbb\xbf" + csv_content.encode("utf-8")
        zf.writestr("blocked-phones.csv", csv_bytes)

        # trackpal-data.json
        json_content = _build_json(
            tenant,
            locale,
            tz,
            clients=clients or [],
            blocked_phones=blocked_phones or [],
        )
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
                db,
                job.id,
                "failed",
                error_code="TENANT_NOT_FOUND",
            )
            return

        # Resolve locale and timezone
        from app.repositories import tenant_settings_repository

        locale = await tenant_settings_repository.resolve_locale(db, job.tenant_id)
        tz = await tenant_settings_repository.resolve_timezone(db, job.tenant_id)

        # Query clients and blocked phones (only those with phones)
        clients = await clients_repository.get_clients_with_user(db, job.tenant_id)
        all_blocks = await blocked_clients_repository.list_active(db, job.tenant_id)

        # Build ZIP
        zip_bytes = await _build_zip(
            tenant, locale, tz, clients=clients, blocked_phones=all_blocks
        )

        # Upload to R2
        storage = get_storage()
        r2_key = generate_random_export_key()
        await storage.upload(r2_key, zip_bytes, content_type="application/zip")

        # Transition to ready
        now = datetime.now(timezone.utc)
        from app.services.export_service import EXPORT_TTL_HOURS

        await export_jobs_repository.update_status(
            db,
            job.id,
            "ready",
            r2_key=r2_key,
            artifact_size_bytes=len(zip_bytes),
            expires_at=now + __import__("datetime").timedelta(hours=EXPORT_TTL_HOURS),
            clear_lease=True,
        )

        logger.info(
            "Export job %s completed — key=%s size=%d",
            job.id,
            r2_key,
            len(zip_bytes),
        )

    except Exception:
        logger.exception("Export job %s failed", job.id)
        # Increment attempts via update
        await export_jobs_repository.update_status(
            db,
            job.id,
            "failed",
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
