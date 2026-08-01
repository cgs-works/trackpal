"""Export worker — claims pending ExportJobs, builds ZIP, honours cancellation, uploads to R2.

Supports:
- 30-minute recoverable lease (anti-duplicate-claim).
- 3 retries with exponential backoff (5s, 25s, 125s).
- Cancellation checkpoints before each expensive operation.
- Atomic replacement: new-ready purges the previous R2 object.
"""

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
from uuid import UUID
from zoneinfo import ZoneInfo

from app.core.database import AsyncSessionLocal
from app.models.blocked_client import BlockedClient
from app.models.client import Client
from app.models.export_job import ExportJob
from app.models.plan import Plan
from app.models.service import Service
from app.models.subscription import Subscription
from app.models.tenant import Tenant
from app.repositories import (
    blocked_clients_repository,
    catalog_repository,
    clients_repository,
    export_jobs_repository,
    tenants_repository,
)
from app.services.export_service import (
    confirm_replacement_ready,
    get_storage,
)
from app.services.export_storage import generate_random_export_key

logger = logging.getLogger(__name__)

_POLL_INTERVAL_S = 5
_MAX_RETRIES = 3
_RETRY_BACKOFF_BASE = 5  # seconds


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
    """Neutralize formula-injection prefixes in CSV values."""
    if value and value[0] in ("=", "+", "-", "@", "\t", "\r", "\n", "|", "%"):
        return "\t" + value
    return value


def _account_status(is_active: bool) -> str:
    """Map client is_active to account_status string."""
    return "active" if is_active else "inactive"


def _build_service_catalog_csv(
    services: Sequence[Service],
    plans_by_service: dict,
    tz: str,
) -> str:
    """Build service-catalog.csv content."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "service_name",
            "service_icon",
            "service_created_on",
            "service_updated_on",
            "plan_name",
            "plan_price",
            "plan_created_on",
            "plan_updated_on",
        ]
    )
    for svc in services:
        plans = plans_by_service.get(svc.id, [])
        if plans:
            for p in plans:
                writer.writerow(
                    [
                        _neutralize_csv_value(svc.name),
                        svc.icon or "",
                        _format_timestamp(svc.created_at, tz),
                        _format_timestamp(svc.updated_at, tz),
                        _neutralize_csv_value(p.name),
                        "" if p.price is None else f"{p.price:.2f}",
                        _format_timestamp(p.created_at, tz),
                        _format_timestamp(p.updated_at, tz),
                    ]
                )
        else:
            writer.writerow(
                [
                    _neutralize_csv_value(svc.name),
                    svc.icon or "",
                    _format_timestamp(svc.created_at, tz),
                    _format_timestamp(svc.updated_at, tz),
                    "",
                    "",
                    "",
                    "",
                ]
            )
    return output.getvalue()


def _build_subscription_snapshot_csv(
    rows: list[tuple[Subscription, Client, Service, Plan]],
    tz: str,
) -> str:
    """Build subscription-snapshot.csv content."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "client_name",
            "client_login_username",
            "service_name",
            "plan_name",
            "service_account_email",
            "service_profile_name",
            "subscription_duration",
            "started_on",
            "expires_on",
            "cancelled_on",
            "subscription_status",
            "recorded_on",
            "last_updated_on",
        ]
    )
    for sub, client, svc, plan in rows:
        writer.writerow(
            [
                _neutralize_csv_value(client.full_name or ""),
                client.username or "",
                _neutralize_csv_value(svc.name),
                _neutralize_csv_value(plan.name),
                sub.streaming_email or "",
                sub.profile_name or "",
                sub.duration_type or "",
                _format_timestamp(sub.starts_at, tz),
                _format_timestamp(sub.expires_at, tz),
                _format_timestamp(sub.cancelled_at, tz),
                sub.status or "",
                _format_timestamp(sub.created_at, tz),
                _format_timestamp(sub.updated_at, tz),
            ]
        )
    return output.getvalue()


# ── ZIP builders ───────────────────────────────────────────────


def _build_account_profile_csv(
    tenant: Tenant, locale: str, tz: str, currency: str | None = None
) -> str:
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
            "currency",
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
            currency or "",
        ]
    )
    return output.getvalue()


def _build_client_data_csv(clients: Sequence[Client], tz: str) -> str:
    """Build client-data.csv content."""
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
    """Build blocked-phones.csv content."""
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
    services: Sequence[Service] | None = None,
    plans_by_service: dict | None = None,
    subscription_rows: list[tuple[Subscription, Client, Service, Plan]] | None = None,
    currency: str | None = None,
) -> str:
    """Build trackpal-data.json content."""
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

    catalog_records = []
    if services:
        for svc in services:
            plans = (plans_by_service or {}).get(svc.id, [])
            plan_records = [
                {
                    "plan_name": p.name,
                    "plan_price": None if p.price is None else f"{p.price:.2f}",
                    "plan_created_on": _format_timestamp(p.created_at, tz) or None,
                    "plan_updated_on": _format_timestamp(p.updated_at, tz) or None,
                }
                for p in plans
            ]
            catalog_records.append(
                {
                    "service_name": svc.name,
                    "service_icon": svc.icon,
                    "service_created_on": _format_timestamp(svc.created_at, tz) or None,
                    "service_updated_on": _format_timestamp(svc.updated_at, tz) or None,
                    "plans": plan_records,
                }
            )

    subscription_records = []
    if subscription_rows:
        for sub, client, svc, plan in subscription_rows:
            subscription_records.append(
                {
                    "client_name": client.full_name or "",
                    "client_login_username": client.username or "",
                    "service_name": svc.name,
                    "plan_name": plan.name,
                    "service_account_email": sub.streaming_email,
                    "service_profile_name": sub.profile_name,
                    "subscription_duration": sub.duration_type,
                    "started_on": _format_timestamp(sub.starts_at, tz) or None,
                    "expires_on": _format_timestamp(sub.expires_at, tz) or None,
                    "cancelled_on": _format_timestamp(sub.cancelled_at, tz) or None,
                    "subscription_status": sub.status,
                    "recorded_on": _format_timestamp(sub.created_at, tz) or None,
                    "last_updated_on": _format_timestamp(sub.updated_at, tz) or None,
                }
            )

    catalog_plan_count = 0
    if services:
        for svc in services:
            catalog_plan_count += len((plans_by_service or {}).get(svc.id, []))

    data = {
        "export_metadata": {
            "export_format_version": "2",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "record_counts": {
                "account_profile": 1,
                "client_accounts": len(client_records),
                "service_catalog": len(catalog_records),
                "catalog_plans": catalog_plan_count,
                "subscription_snapshot": len(subscription_records),
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
            "currency": currency,
        },
        "client_accounts": client_records,
        "service_catalog": catalog_records,
        "subscription_snapshot": subscription_records,
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
  account-profile.csv    — Your account profile in CSV format (UTF-8 with BOM)
  client-data.csv        — Your client records in CSV format (UTF-8 with BOM)
  service-catalog.csv    — Your services and plans in CSV format (UTF-8 with BOM)
  subscription-snapshot.csv — Your current subscription records in CSV format (UTF-8 with BOM)
  blocked-phones.csv     — Phone-based access control blocks in CSV format (UTF-8 with BOM)
  trackpal-data.json     — All data sections in JSON format (UTF-8)

Fields in account-profile.csv / account_profile in trackpal-data.json:
  account_name         — The name of your business
  contact_email        — The contact email for your business
  whatsapp_phone       — The WhatsApp phone number linked to your account
  login_username       — Your login username
  current_plan         — Your current plan (starter or pro)
  preferred_language   — Your preferred language (en or es)
  time_zone             — Your configured time zone
  currency             — Your configured currency (ISO 4217 code, empty when unset)

Fields in client-data.csv / client_accounts in trackpal-data.json:
  client_name          — The full name of the client
  login_username       — The client login username
  whatsapp_phone       — The WhatsApp phone number of the client
  account_status       — Whether the client is active or inactive
  registered_on        — When the client was registered (timezone of your account)
  last_updated_on      — When the client was last updated (timezone of your account)

Fields in service-catalog.csv / service_catalog in trackpal-data.json:
  service_name         — The name of the service
  service_icon         — The optional Iconify "prefix:name" reference (e.g. "simple-icons:netflix"). TrackPal does not include the SVG asset.
  service_created_on   — When the service was added (timezone of your account)
  service_updated_on   — When the service was last updated (timezone of your account)
  plan_name            — The name of the plan (empty when a service has no plans)
  plan_price           — The plan price (empty when not set)
  plan_created_on      — When the plan was added (empty when a service has no plans)
  plan_updated_on      — When the plan was last updated (empty when a service has no plans)

Fields in subscription-snapshot.csv / subscription_snapshot in trackpal-data.json:
  client_name              — The full name of the client subscribed
  client_login_username    — The client login username
  service_name             — The name of the service
  plan_name                — The name of the plan
  service_account_email    — The streaming account email
  service_profile_name     — The streaming profile name (if any)
  subscription_duration    — The duration type (e.g. 1_month, 3_months, 6_months, 1_year)
  started_on               — When the subscription started
  expires_on               — When the subscription expires
  cancelled_on             — When the subscription was cancelled (if applicable)
  subscription_status      — The current status (active, expired, cancelled, suspended)
  recorded_on              — When the subscription was recorded
  last_updated_on          — When the subscription was last updated

Fields in blocked-phones.csv / blocked_phone_list in trackpal-data.json:
  phone                — The blocked phone number (digits only)
  blocked_at           — When the block was created (timezone of your account)

Notes:
  - CSV files use UTF-8 with BOM for compatible spreadsheet opening.
  - CSV values that could be interpreted as formulas are prefixed with
    a tab character to prevent accidental execution.
  - JSON uses null for unset optional fields.
  - A service with no plans produces a single CSV row with empty plan
    fields and a JSON entry with an empty plans list.
  - Access control blocks that contain only a WhatsApp LID (no phone
    number) are deliberately omitted from both formats.
  - The subscription snapshot includes all subscription records
    (active, expired, cancelled), not just active ones.
  - Subscription lifecycle events and reminder logs are not included.
  - This is a point-in-time snapshot. Changes made after the export
    generation will appear in a later export.
  - No passwords, tokens, secrets, or internal identifiers are included.
  - Duration codes (e.g. 1_month, 1_year) and status codes (e.g. active,
    expired, cancelled) use stable English values.
  - Downloaded copies do not expire and become your responsibility.
"""

_README_ES = """Exportación de datos de TrackPal — Mi cuenta
=================================================

Este archivo contiene una instantánea de los datos de tu cuenta
registrados al momento de la generación indicada en
trackpal-data.json.

Archivos incluidos:
  account-profile.csv    — Perfil de tu cuenta en formato CSV (UTF-8 con BOM)
  client-data.csv        — Registros de clientes en formato CSV (UTF-8 con BOM)
  service-catalog.csv    — Tus servicios y planes en formato CSV (UTF-8 con BOM)
  subscription-snapshot.csv — Registros actuales de suscripciones en CSV (UTF-8 con BOM)
  blocked-phones.csv     — Bloques de acceso por teléfono en formato CSV (UTF-8 con BOM)
  trackpal-data.json     — Todas las secciones de datos en formato JSON (UTF-8)

Campos en account-profile.csv / account_profile en trackpal-data.json:
  account_name         — El nombre de tu negocio
  contact_email        — El correo de contacto de tu negocio
  whatsapp_phone       — El número de WhatsApp vinculado a tu cuenta
  login_username       — Tu nombre de usuario de inicio de sesión
  current_plan         — Tu plan actual (starter o pro)
  preferred_language   — Tu idioma preferido (en o es)
  time_zone             — Tu zona horaria configurada
  currency             — Tu moneda configurada (código ISO 4217, vacío si no está establecida)

Campos en client-data.csv / client_accounts en trackpal-data.json:
  client_name          — El nombre completo del cliente
  login_username       — El nombre de usuario del cliente
  whatsapp_phone       — El número de WhatsApp del cliente
  account_status       — Si el cliente está activo o inactivo
  registered_on        — Cuándo se registró el cliente (zona horaria de tu cuenta)
  last_updated_on      — Cuándo se actualizó por última vez (zona horaria de tu cuenta)

Campos en service-catalog.csv / service_catalog en trackpal-data.json:
  service_name         — El nombre del servicio
  service_icon         — La referencia opcional Iconify "prefix:name" (ej. "simple-icons:netflix"). TrackPal no incluye el recurso SVG.
  service_created_on   — Cuándo se agregó el servicio (zona horaria de tu cuenta)
  service_updated_on   — Cuándo se actualizó el servicio por última vez
  plan_name            — El nombre del plan (vacío si el servicio no tiene planes)
  plan_price           — El precio del plan (vacío si no está establecido)
  plan_created_on      — Cuándo se agregó el plan (vacío si el servicio no tiene planes)
  plan_updated_on      — Cuándo se actualizó el plan por última vez

Campos en subscription-snapshot.csv / subscription_snapshot en trackpal-data.json:
  client_name              — El nombre completo del suscriptor
  client_login_username    — El nombre de usuario del cliente
  service_name             — El nombre del servicio
  plan_name                — El nombre del plan
  service_account_email    — El correo electrónico de la cuenta de streaming
  service_profile_name     — El nombre del perfil de streaming (si existe)
  subscription_duration    — El tipo de duración (ej. 1_month, 3_months, 6_months, 1_year)
  started_on               — Cuándo comenzó la suscripción
  expires_on               — Cuándo vence la suscripción
  cancelled_on             — Cuándo se canceló la suscripción (si aplica)
  subscription_status      — El estado actual (active, expired, cancelled, suspended)
  recorded_on              — Cuándo se registró la suscripción
  last_updated_on          — Cuándo se actualizó la suscripción por última vez

Campos en blocked-phones.csv / blocked_phone_list en trackpal-data.json:
  phone                — El número de teléfono bloqueado (solo dígitos)
  blocked_at           — Cuándo se creó el bloqueo (zona horaria de tu cuenta)

Notas:
  - Los archivos CSV usan UTF-8 con BOM para apertura compatible en hojas
    de cálculo.
  - Los valores CSV que podrían interpretarse como fórmulas tienen un
    prefijo de tabulación para evitar ejecución accidental.
  - JSON usa null para campos opcionales no establecidos.
  - Un servicio sin planes produce una fila CSV con campos de plan vacíos
    y una entrada JSON con una lista de planes vacía.
  - Los bloques de control de acceso que contienen solo un WhatsApp LID
    (sin número telefónico) se omiten deliberadamente de ambos formatos.
  - La instantánea de suscripciones incluye todos los registros (activos,
    vencidos, cancelados), no solo los activos.
  - Los eventos del ciclo de vida de suscripciones y registros de
    recordatorios no están incluidos.
  - Esta es una instantánea puntual. Los cambios realizados después de la
    generación aparecerán en una exportación posterior.
  - No se incluyen contraseñas, tokens, secretos ni identificadores
    internos.
  - Los códigos de duración (ej. 1_month, 1_year) y estado (ej. active,
    expired, cancelled) usan valores estables en inglés.
  - Las copias descargadas no expiran y son tu responsabilidad.
"""


async def _build_zip(
    tenant: Tenant,
    locale: str,
    tz: str,
    *,
    clients: Sequence[Client] | None = None,
    blocked_phones: Sequence[BlockedClient] | None = None,
    services: Sequence[Service] | None = None,
    plans_by_service: dict | None = None,
    subscription_rows: list[tuple[Subscription, Client, Service, Plan]] | None = None,
    currency: str | None = None,
) -> bytes:
    """Build the export ZIP for the given tenant."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        csv_content = _build_account_profile_csv(tenant, locale, tz, currency=currency)
        csv_bytes = b"\xef\xbb\xbf" + csv_content.encode("utf-8")
        zf.writestr("account-profile.csv", csv_bytes)

        csv_content = _build_client_data_csv(clients or [], tz)
        csv_bytes = b"\xef\xbb\xbf" + csv_content.encode("utf-8")
        zf.writestr("client-data.csv", csv_bytes)

        csv_content = _build_service_catalog_csv(
            services or [], plans_by_service or {}, tz
        )
        csv_bytes = b"\xef\xbb\xbf" + csv_content.encode("utf-8")
        zf.writestr("service-catalog.csv", csv_bytes)

        csv_content = _build_subscription_snapshot_csv(subscription_rows or [], tz)
        csv_bytes = b"\xef\xbb\xbf" + csv_content.encode("utf-8")
        zf.writestr("subscription-snapshot.csv", csv_bytes)

        csv_content = _build_blocked_phones_csv(blocked_phones or [], tz)
        csv_bytes = b"\xef\xbb\xbf" + csv_content.encode("utf-8")
        zf.writestr("blocked-phones.csv", csv_bytes)

        json_content = _build_json(
            tenant,
            locale,
            tz,
            clients=clients or [],
            blocked_phones=blocked_phones or [],
            services=services or [],
            plans_by_service=plans_by_service or {},
            subscription_rows=subscription_rows or [],
            currency=currency,
        )
        zf.writestr("trackpal-data.json", json_content.encode("utf-8"))

        readme_content = _build_readme(locale)
        zf.writestr("README.txt", readme_content.encode("utf-8"))

    return buffer.getvalue()


# ── Cancellation check ─────────────────────────────────────────


async def _is_cancelled(db: AsyncSessionLocal, job_id: UUID) -> bool:
    """Check if a job has been cancelled (polled by the worker)."""
    job = await export_jobs_repository.get_by_id(db, job_id)
    return job is None or job.status == "cancelled"


# ── Worker processing ─────────────────────────────────────────


async def _process_job_with_session(
    db: AsyncSessionLocal,  # type: ignore[valid-type]
    job: ExportJob,
) -> None:
    """Process one export job with a given DB session.

    Supports retry with backoff and cancellation checkpoints.
    """
    for attempt in range(job.max_attempts):
        # ── Cancellation checkpoint ──
        if await _is_cancelled(db, job.id):
            logger.info("Export job %s was cancelled — aborting", job.id)
            return

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

            # ── Cancellation checkpoint ──
            if await _is_cancelled(db, job.id):
                return

            # Resolve locale and timezone
            from app.repositories import tenant_settings_repository

            locale = await tenant_settings_repository.resolve_locale(db, job.tenant_id)
            tz = await tenant_settings_repository.resolve_timezone(db, job.tenant_id)
            currency = await tenant_settings_repository.resolve_currency(
                db, job.tenant_id
            )

            # ── Cancellation checkpoint ──
            if await _is_cancelled(db, job.id):
                return

            # Query clients and blocked phones
            clients = await clients_repository.get_clients_with_user(db, job.tenant_id)
            all_blocks = await blocked_clients_repository.list_active(db, job.tenant_id)

            # ── Cancellation checkpoint ──
            if await _is_cancelled(db, job.id):
                return

            # Query catalog
            (
                services,
                plans_by_service,
            ) = await catalog_repository.list_services_with_plans(db, job.tenant_id)

            # ── Cancellation checkpoint ──
            if await _is_cancelled(db, job.id):
                return

            # Query subscription records
            subscription_rows = (
                await catalog_repository.list_all_subscriptions_for_export(
                    db, job.tenant_id
                )
            )

            # ── Cancellation checkpoint ──
            if await _is_cancelled(db, job.id):
                return

            # Build ZIP
            zip_bytes = await _build_zip(
                tenant,
                locale,
                tz,
                clients=clients,
                blocked_phones=all_blocks,
                services=services,
                plans_by_service=plans_by_service,
                subscription_rows=subscription_rows,
                currency=currency,
            )

            # ── Cancellation checkpoint ──
            if await _is_cancelled(db, job.id):
                return

            # Upload to R2
            storage = get_storage()
            r2_key = generate_random_export_key()
            await storage.upload(r2_key, zip_bytes, content_type="application/zip")

            # ── Cancellation checkpoint (post-upload, pre-commit) ──
            if await _is_cancelled(db, job.id):
                # Purge the partial upload
                try:
                    await storage.delete(r2_key)
                except Exception:
                    logger.warning(
                        "Failed to purge partial upload %s after cancel", r2_key
                    )
                return

            # Atomic replacement: mark ready and purge previous
            await confirm_replacement_ready(
                db,
                job.id,
                tenant_id=job.tenant_id,
                r2_key=r2_key,
                artifact_size_bytes=len(zip_bytes),
            )

            logger.info(
                "Export job %s completed — key=%s size=%d",
                job.id,
                r2_key,
                len(zip_bytes),
            )
            return  # success

        except Exception:
            logger.exception(
                "Export job %s attempt %d/%d failed",
                job.id,
                attempt + 1,
                job.max_attempts,
            )
            await export_jobs_repository.increment_attempts(db, job.id)

            is_last_attempt = attempt + 1 >= job.max_attempts
            if is_last_attempt:
                await export_jobs_repository.update_status(
                    db,
                    job.id,
                    "failed",
                    error_code="GENERATION_ERROR",
                )
                return

            # Backoff before retry
            backoff_seconds = _RETRY_BACKOFF_BASE * (5**attempt)
            logger.info(
                "Retrying job %s in %ds (attempt %d/%d)",
                job.id,
                backoff_seconds,
                attempt + 2,
                job.max_attempts,
            )

            # Check cancellation during backoff in 1s intervals
            for _ in range(backoff_seconds):
                await asyncio.sleep(1)
                if await _is_cancelled(db, job.id):
                    logger.info("Export job %s cancelled during backoff", job.id)
                    return

            # Reset to pending for retry
            await export_jobs_repository.update_status(
                db,
                job.id,
                "pending",
                clear_lease=True,
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
