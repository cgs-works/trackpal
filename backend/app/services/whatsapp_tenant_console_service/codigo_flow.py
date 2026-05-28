"""Codigo lookup flow — 2-step dialog (service then target email).

Flow structure:
1. User triggers with ``codigo|código|code`` → show service list
2. User selects service → ask for target email
3. User provides email → create lookup job, store job_id in session temp_data
"""

from __future__ import annotations

import logging

from app.core.i18n import t as _i18n_t
from app.core.redis_client import get_redis_manager
from app.repositories import (
    mailbox_config_repository,
    mailbox_lookup_repository,
)
from app.services.mail_lookup_worker import enqueue_job

from . import _context as ctx

logger = logging.getLogger(__name__)

# Format helpers for service list display
_CODIGO_SERVICE_LABELS: dict[str, str] = {
    "netflix": "Netflix",
    "disney": "Disney+",
    "hbo_max": "HBO Max",
    "prime_video": "Prime Video",
    "spotify": "Spotify",
    "universal_plus": "Universal+",
}


async def _start_codigo_flow(self, phone, session_service, tenant_id, db):
    """Entry point — show list of available services for code lookup."""
    loc = ctx.get_locale()

    # Check mailbox is configured
    if tenant_id is not None and db is not None:
        mailbox = await mailbox_config_repository.get_by_tenant(db, tenant_id)
        if mailbox is None:
            return self._t(self.KEY_CODIGO_NO_MAILBOX)
        if mailbox.status not in ("connected", "error"):
            return self._t(self.KEY_CODIGO_NO_MAILBOX)

    # Build service list
    lines = []
    for i, key in enumerate(self.STREAMING_SERVICE_KEYS, start=1):
        label = _CODIGO_SERVICE_LABELS.get(key, key.capitalize())
        lines.append(f"{i}️⃣ {label}")
    lines.append("0️⃣ " + _i18n_t(loc, "wa.tenant.codigo.cancel"))

    service_list = "\n".join(lines)

    # Create session with flow state
    session = await session_service.get_session(f"admin:{phone}")
    if session is None:
        session = await session_service.create_session(f"admin:{phone}")

    session.flow = self.CODIGO_FLOW
    session.step = self.CODIGO_STEP_SERVICE
    session.temp_data = {}
    await session_service.save_session(session)

    return self._t(self.KEY_CODIGO_SERVICE_PROMPT, service_list=service_list)


async def _handle_codigo_service(
    self, phone, msg, session, session_service, tenant_id, db
):
    """Handle service selection — store service_key, ask for email."""
    loc = ctx.get_locale()

    # Parse selection
    try:
        idx = int(msg.strip())
    except ValueError:
        return self._t(self.KEY_CODIGO_INVALID_SERVICE)

    if idx < 1 or idx > len(self.STREAMING_SERVICE_KEYS):
        if idx == 0:
            # Cancel — reset flow
            await session_service.clear_session(f"admin:{phone}")
            return self._with_main_menu(_i18n_t(loc, "wa.tenant.cancelled"), locale=loc)
        return self._t(self.KEY_CODIGO_INVALID_SERVICE)

    service_key = self.STREAMING_SERVICE_KEYS[idx - 1]
    label = _CODIGO_SERVICE_LABELS.get(service_key, service_key.capitalize())

    # Store selection and advance step
    session.temp_data["service_key"] = service_key
    session.temp_data["service_label"] = label
    session.step = self.CODIGO_STEP_EMAIL
    await session_service.save_session(session)

    return self._t(self.KEY_CODIGO_EMAIL_PROMPT, service_label=label)


async def _handle_codigo_email(
    self, phone, msg, session, session_service, tenant_id, db
):
    """Handle email input — create lookup job, store job_id in session."""
    loc = ctx.get_locale()

    target_email = msg.strip()
    if (
        not target_email
        or len(target_email) < 3
        or "@" not in target_email
        or "." not in target_email.split("@", 1)[1]
    ):
        return _i18n_t(loc, "wa.tenant.codigo.invalid_email")

    service_key = session.temp_data.get("service_key")
    if not service_key:
        # Stale session — bail out
        await session_service.clear_session(f"admin:{phone}")
        return self._with_main_menu(_i18n_t(loc, "wa.tenant.cancelled"), locale=loc)

    # Create lookup job
    if tenant_id is None or db is None:
        logger.error("Cannot create lookup job: missing tenant_id or db")
        return self._t(self.KEY_CODIGO_ERROR)

    mailbox = await mailbox_config_repository.get_by_tenant(db, tenant_id)
    if mailbox is None:
        return self._t(self.KEY_CODIGO_NO_MAILBOX)

    try:
        job = await mailbox_lookup_repository.create_job(
            db,
            tenant_id=tenant_id,
            mailbox_id=mailbox.id,
            service_key=service_key,
            target_email=target_email,
        )
        await db.flush()

        # Enqueue to Redis for worker processing
        manager = get_redis_manager()
        if manager is not None:
            try:
                await enqueue_job(manager, job.id)
            except Exception:
                logger.exception(
                    "Failed to enqueue lookup job %s for tenant %s",
                    job.id,
                    tenant_id,
                )
                await db.delete(job)
                await db.flush()
                return self._t(self.KEY_CODIGO_ERROR)
    except Exception:
        logger.exception("Failed to create lookup job for tenant %s", tenant_id)
        return self._t(self.KEY_CODIGO_ERROR)

    # Store job_id in session so facade can retrieve it
    session.temp_data["pending_job_id"] = str(job.id)
    session.temp_data["target_email"] = target_email
    # Job created — clear flow state
    session.flow = ""
    session.step = ""
    await session_service.save_session(session)

    return _i18n_t(loc, "wa.tenant.codigo.buscando")
