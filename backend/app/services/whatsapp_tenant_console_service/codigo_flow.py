"""Codigo lookup flow — 2-step dialog (service then target email).

Flow structure:
1. User triggers with ``codigo|código|code`` → show service list
2. User selects service → ask for target email
3. User provides email → create lookup job, store job_id in session temp_data
"""

from __future__ import annotations

import logging
from typing import Any

from app.core.i18n import t as _i18n_t

from uuid import UUID

from app.repositories import (
    code_services_repository,
    mailbox_config_repository,
    mailbox_lookup_repository,
)
from app.services.whatsapp_navigation import is_back, is_cancel

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

_PAGE_SIZE = 7


def _build_service_page(
    effective_keys: list[str],
    page: int,
    loc: str,
    started_from_menu: bool,
) -> str:
    """Build formatted service list for a given page.

    Service options use ``[N]`` format (page-relative 1-7). Navigation
    options ``8  `` (previous), ``9  `` (next), and ``0  `` (cancel) use
    emoji to avoid confusion.
    """
    total = len(effective_keys)
    total_pages = (total + _PAGE_SIZE - 1) // _PAGE_SIZE
    start = page * _PAGE_SIZE
    end = min(start + _PAGE_SIZE, total)

    lines: list[str] = []
    for i in range(start, end):
        rel = i - start + 1
        key = effective_keys[i]
        label = _CODIGO_SERVICE_LABELS.get(key, key.capitalize())
        lines.append(f"[{rel}] {label}")

    if total_pages > 1:
        lines.append("")
        if page > 0:
            lines.append("8️⃣ " + _i18n_t(loc, "wa.tenant.codigo.prev_page"))
        if page < total_pages - 1:
            lines.append("9️⃣ " + _i18n_t(loc, "wa.tenant.codigo.next_page"))

    cancel_key = (
        "wa.tenant.codigo.cancel"
        if started_from_menu
        else "wa.tenant.codigo.cancel_direct"
    )
    lines.append("")
    lines.append("0️⃣ " + _i18n_t(loc, cancel_key))

    return "\n".join(lines)


async def _start_codigo_flow(
    self,
    phone: str,
    session_service: Any,
    tenant_id: Any,
    db: Any,
    *,
    started_from_menu: bool = False,
    role: str = "tenant",
) -> str:
    """Entry point -- show list of available services for code lookup."""
    loc = ctx.get_locale()

    # Check mailbox is configured
    if tenant_id is not None and db is not None:
        mailbox = await mailbox_config_repository.get_by_tenant(db, tenant_id)
        if mailbox is None:
            return self._t(self.KEY_CODIGO_NO_MAILBOX)
        if mailbox.status not in ("connected", "error"):
            return self._t(self.KEY_CODIGO_NO_MAILBOX)

    # Get effective service list (tenant_selected ∩ global_active)
    effective_keys: list[str] = []
    if tenant_id is not None and db is not None:
        effective_keys = await code_services_repository.get_effective_service_keys(
            db, tenant_id
        )

    if not effective_keys:
        if role == "client":
            return self._t(self.KEY_CODIGO_NO_CODE_SERVICES_CLIENT)
        return self._t(self.KEY_CODIGO_NO_CODE_SERVICES_TENANT)

    # Build page 1 of services
    service_list = _build_service_page(
        effective_keys, 0, loc, started_from_menu
    )

    # Create session with flow state
    session = await session_service.get_session(f"admin:{phone}")
    if session is None:
        session = await session_service.create_session(f"admin:{phone}")

    session.flow = self.CODIGO_FLOW
    session.step = self.CODIGO_STEP_SERVICE
    session.temp_data = {
        "codigo_started_from_menu": "true" if started_from_menu else "false",
        "codigo_effective_keys": effective_keys,
        "codigo_current_page": 0,
    }
    await session_service.save_session(session)

    return self._t(self.KEY_CODIGO_SERVICE_PROMPT, service_list=service_list)


async def _handle_codigo_service(
    self,
    phone: str,
    msg: str,
    session: Any,
    session_service: Any,
    tenant_id: Any,
    db: Any,
) -> str:
    """Handle service selection — store service_key, ask for email."""
    loc = ctx.get_locale()

    # Use effective keys from session (set during _start_codigo_flow)
    effective_keys = session.temp_data.get("codigo_effective_keys", [])
    if not effective_keys:
        # Recompute from authoritative DB source; never fallback to global list.
        if tenant_id is None or db is None:
            await session_service.clear_session(f"admin:{phone}")
            return self._with_main_menu(_i18n_t(loc, "wa.tenant.cancelled"), locale=loc)
        effective_keys = await code_services_repository.get_effective_service_keys(
            db, tenant_id
        )
        if not effective_keys:
            await session_service.clear_session(f"admin:{phone}")
            return self._with_main_menu(
                self._t(self.KEY_CODIGO_NO_CODE_SERVICES_TENANT), locale=loc
            )
        session.temp_data["codigo_effective_keys"] = effective_keys
        await session_service.save_session(session)

    # Check cancel first
    if is_cancel(msg):
        started_from_menu = (
            session.temp_data.get("codigo_started_from_menu") == "true"
        )
        await session_service.clear_session(f"admin:{phone}")
        if started_from_menu:
            return self._with_main_menu(
                _i18n_t(loc, "wa.tenant.cancelled"), locale=loc
            )
        return _i18n_t(loc, "wa.tenant.cancelled")

    if is_back(msg):
        await session_service.clear_session(f"admin:{phone}")
        return self._with_main_menu(_i18n_t(loc, "wa.tenant.cancelled"), locale=loc)

    # Parse selection (supports pagination)
    try:
        idx = int(msg.strip())
    except ValueError:
        return self._t(self.KEY_CODIGO_INVALID_SERVICE)

    current_page = session.temp_data.get("codigo_current_page", 0)
    total = len(effective_keys)
    total_pages = (total + _PAGE_SIZE - 1) // _PAGE_SIZE

    # Pagination: next page
    if idx == 9 and total_pages > 1 and current_page < total_pages - 1:
        session.temp_data["codigo_current_page"] = current_page + 1
        await session_service.save_session(session)
        service_list = _build_service_page(
            effective_keys,
            current_page + 1,
            loc,
            session.temp_data.get("codigo_started_from_menu") == "true",
        )
        return self._t(self.KEY_CODIGO_SERVICE_PROMPT, service_list=service_list)

    # Pagination: previous page
    if idx == 8 and total_pages > 1 and current_page > 0:
        session.temp_data["codigo_current_page"] = current_page - 1
        await session_service.save_session(session)
        service_list = _build_service_page(
            effective_keys,
            current_page - 1,
            loc,
            session.temp_data.get("codigo_started_from_menu") == "true",
        )
        return self._t(self.KEY_CODIGO_SERVICE_PROMPT, service_list=service_list)

    # Validate index within current page
    if idx < 1 or idx > _PAGE_SIZE:
        return self._t(self.KEY_CODIGO_INVALID_SERVICE)

    actual_idx = current_page * _PAGE_SIZE + (idx - 1)
    if actual_idx >= total:
        return self._t(self.KEY_CODIGO_INVALID_SERVICE)

    service_key = effective_keys[actual_idx]
    label = _CODIGO_SERVICE_LABELS.get(service_key, service_key.capitalize())

    # Store selection and advance step
    session.temp_data["service_key"] = service_key
    session.temp_data["service_label"] = label
    session.step = self.CODIGO_STEP_EMAIL
    await session_service.save_session(session)

    return self._t(self.KEY_CODIGO_EMAIL_PROMPT, service_label=label)


async def _handle_codigo_email(
    self,
    phone: str,
    msg: str,
    session: Any,
    session_service: Any,
    tenant_id: Any,
    db: Any,
) -> str:
    """Handle email input — store lookup intent for handler orchestration.

    No longer creates jobs or enqueues to Redis.  Stores intent data
    in session so the central tenant handler (``_handle_tenant_console``)
    can create the job durably after this flow returns.
    """
    loc = ctx.get_locale()

    # Check cancel
    if is_cancel(msg):
        await session_service.clear_session(f"admin:{phone}")
        return _i18n_t(loc, "wa.tenant.cancelled")

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

    # Store lookup intent in session for handler to process durably
    session.temp_data["service_key"] = service_key
    session.temp_data["target_email"] = target_email
    session.temp_data["pending_lookup_intent"] = "true"
    # Keep session alive in awaiting_result so user can retry/back/cancel
    # after n8n delivers the result notification.
    session.flow = self.CODIGO_FLOW
    session.step = self.CODIGO_STEP_AWAITING_RESULT
    await session_service.save_session(session)

    return _i18n_t(loc, "wa.tenant.codigo.buscando")


async def _handle_codigo_awaiting_result(
    self,
    phone: str,
    msg: str,
    session: Any,
    session_service: Any,
    tenant_id: Any,
    db: Any,
) -> str:
    """Handle user response after the lookup result notification.

    The session is kept alive (step=awaiting_result) while n8n polls
    the job and sends the result directly to the user.  When the user
    replies to the result message the backend receives it through
    the normal console endpoint and routes here.
    """
    loc = ctx.get_locale()

    if is_cancel(msg):
        await session_service.clear_session(f"admin:{phone}")
        return _i18n_t(loc, "wa.tenant.cancelled")

    # Check lookup job status from DB
    job_done = False
    lookup_job_id = session.temp_data.get("lookup_job_id")
    if lookup_job_id:
        try:
            job = await mailbox_lookup_repository.get_job(
                db,
                UUID(lookup_job_id),
                tenant_id=tenant_id,
            )
            job_done = job is not None and job.status in (
                "completed", "failed", "timeout"
            )
        except Exception:
            logger.exception(
                "Failed to check lookup job %s", lookup_job_id,
            )
            job_done = True  # treat error as done so we don't loop

    if msg.strip() == "1":
        service_key = session.temp_data.get("service_key", "")
        target_email = session.temp_data.get("target_email", "")
        if service_key and target_email:
            session.temp_data["pending_lookup_intent"] = "true"
            await session_service.save_session(session)
            return _i18n_t(loc, "wa.tenant.codigo.buscando")

        # Fallback — restart from service list
        effective_keys = (
            await code_services_repository.get_effective_service_keys(
                db, tenant_id
            )
        )
        if not effective_keys:
            await session_service.clear_session(f"admin:{phone}")
            return self._t(self.KEY_CODIGO_NO_CODE_SERVICES_TENANT)

        await session_service.clear_session(f"admin:{phone}")
        new_session = await session_service.create_session(
            f"admin:{phone}"
        )
        new_session.flow = self.CODIGO_FLOW
        new_session.step = self.CODIGO_STEP_SERVICE
        new_session.temp_data = {
            "codigo_effective_keys": effective_keys,
            "codigo_current_page": 0,
        }
        await session_service.save_session(new_session)
        service_list = _build_service_page(
            effective_keys, 0, loc, started_from_menu=False,
        )
        return self._t(
            self.KEY_CODIGO_SERVICE_PROMPT, service_list=service_list,
        )

    if msg.strip() == "2":
        effective_keys = (
            await code_services_repository.get_effective_service_keys(
                db, tenant_id
            )
        )
        if not effective_keys:
            await session_service.clear_session(f"admin:{phone}")
            return self._t(self.KEY_CODIGO_NO_CODE_SERVICES_TENANT)

        await session_service.clear_session(f"admin:{phone}")
        new_session = await session_service.create_session(
            f"admin:{phone}"
        )
        new_session.flow = self.CODIGO_FLOW
        new_session.step = self.CODIGO_STEP_SERVICE
        new_session.temp_data = {
            "codigo_effective_keys": effective_keys,
            "codigo_current_page": 0,
        }
        await session_service.save_session(new_session)
        service_list = _build_service_page(
            effective_keys, 0, loc, started_from_menu=False,
        )
        return self._t(
            self.KEY_CODIGO_SERVICE_PROMPT, service_list=service_list,
        )

    if msg.strip() == "0":
        # Cancel
        await session_service.clear_session(f"admin:{phone}")
        return _i18n_t(loc, "wa.tenant.cancelled")

    # Unknown input — keep session alive
    return _i18n_t(loc, "wa.tenant.codigo.still_checking")
