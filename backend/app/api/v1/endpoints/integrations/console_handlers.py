"""WhatsApp console handlers for master, tenant, and client roles.

Functions are called from ``console.py`` after instance-first routing
has resolved the caller's identity/role.
"""

from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.i18n import t as _i18n_t
from app.core.phone import normalize_phone
from app.core.redis_client import RedisUnavailableError, get_redis_manager
from app.schemas.whatsapp import WhatsAppConsoleResponse
from app.repositories import (
    client_messaging_block_repository,
    clients_repository,
    code_services_repository,
    mailbox_config_repository,
    mailbox_lookup_repository,
    tenants_repository,
)
from app.services.mail_lookup_worker import enqueue_job
from app.services.auth_service import AuthService
from app.services.catalog_service import CatalogService
from app.services.client_service import ClientService
from app.services.contingency_reply_policy import ContingencyReplyPolicy

from app.services.profile_service import ProfileService
from app.services.subscription_service import SubscriptionService
from app.services.tenant_service import TenantService
from app.services.whatsapp_auth_session_service import WhatsAppAuthSessionService
from app.services.whatsapp_client_console_facade import WhatsAppClientConsoleFacade
from app.services.whatsapp_console_service import WhatsAppConsoleService
from app.services.whatsapp_master_console_facade import WhatsAppMasterConsoleFacade
from app.services.whatsapp_session_service import WhatsAppSessionService
from app.services.whatsapp_tenant_console_facade import WhatsAppTenantConsoleFacade
from app.services.whatsapp_tenant_console_service import WhatsAppTenantConsoleService
from app.api.v1.endpoints.integrations.adapter import (
    _TenantConsoleAdapter,
    UNKNOWN_PHONE_REPLY,
)

logger = logging.getLogger(__name__)

# ── Unauthenticated code lookup constants ──────────────────────────
_UNAUTH_CODIGO_FLOW = "codigo"
_UNAUTH_CODIGO_STEP_SERVICE = "service"
_UNAUTH_CODIGO_STEP_EMAIL = "email"

_UNAUTH_CODIGO_SERVICE_LABELS: dict[str, str] = {
    "netflix": "Netflix",
    "disney": "Disney+",
    "hbo_max": "HBO Max",
    "prime_video": "Prime Video",
    "spotify": "Spotify",
    "universal_plus": "Universal+",
}


def _unauth_session_key(phone_digits: str, sender_lid: str | None) -> str:
    """Session key for unregistered identity code lookup."""
    if phone_digits:
        return f"unreg:{phone_digits}"
    if sender_lid:
        return f"unreg:{sender_lid}"
    return "unreg:unknown"


auth_service = AuthService()
console_service = WhatsAppConsoleService()
tenant_service = TenantService()

CONSOLE_STATE_UNAVAILABLE_REPLY = ContingencyReplyPolicy.TEMPORARY_UNAVAILABLE

# ====================================================================
# Master console handler
# ====================================================================


async def _handle_master_console(
    phone: str,
    message: str,
    instance: str | None,
    manager: object,
    db: AsyncSession,
) -> WhatsAppConsoleResponse:
    """Handle message from identified Master user."""
    session_service = WhatsAppSessionService(
        connection_manager=manager,
        ttl_seconds=settings.whatsapp_session_ttl_minutes * 60,
    )

    auth_session_service = WhatsAppAuthSessionService(
        connection_manager=manager,
        session_ttl_seconds=settings.whatsapp_session_ttl_minutes * 60,
        fail_threshold=settings.whatsapp_auth_fail_threshold,
        lock_minutes=settings.whatsapp_auth_lock_minutes,
        fail_window_minutes=settings.whatsapp_auth_fail_window_minutes,
    )

    adapter = _TenantConsoleAdapter(tenant_service, db)
    facade = WhatsAppMasterConsoleFacade(
        console_service=console_service,
        session_service=session_service,
        auth_session_service=auth_session_service,
        tenant_service=adapter,
    )

    try:
        reply = await facade.process_message(
            phone=phone,
            message=message,
            instance=instance,
            db=db,
        )
    except (RedisUnavailableError, ConnectionError, TimeoutError, OSError):
        return WhatsAppConsoleResponse(reply=CONSOLE_STATE_UNAVAILABLE_REPLY)
    return WhatsAppConsoleResponse(reply=reply)


# ====================================================================
# Tenant console handler
# ====================================================================


async def _handle_tenant_console(
    phone: str,
    message: str,
    instance: str | None,
    manager: object,
    db: AsyncSession,
) -> WhatsAppConsoleResponse:
    """Handle message from identified Tenant Admin user."""
    session_service = WhatsAppSessionService(
        connection_manager=manager,
        ttl_seconds=settings.whatsapp_session_ttl_minutes * 60,
    )

    tenant_console_service = WhatsAppTenantConsoleService(
        client_service=ClientService(),
        catalog_service=CatalogService(),
        profile_service=ProfileService(),
        subscription_service=SubscriptionService(),
    )

    facade = WhatsAppTenantConsoleFacade(
        console_service=tenant_console_service,
        session_service=session_service,
        tenant_service=TenantService(),
    )

    identity = await auth_service.identify_by_phone(db, phone)
    if identity is None:
        return WhatsAppConsoleResponse(reply=UNKNOWN_PHONE_REPLY)

    try:
        reply = await facade.process_message(
            phone=phone,
            message=message,
            identity=identity,
            instance=instance,
            db=db,
        )
    except (RedisUnavailableError, ConnectionError, TimeoutError, OSError):
        return WhatsAppConsoleResponse(reply=CONSOLE_STATE_UNAVAILABLE_REPLY)

    # === Lookup job orchestration (for codigo flow intent) ===
    lookup_job_id: str | None = None
    tenant_id_out: str | None = None
    session = None

    try:
        session = await session_service.get_session(f"admin:{phone}")
        has_lookup_intent = (
            session is not None
            and session.temp_data.get("pending_lookup_intent") == "true"
        )
        if has_lookup_intent:
            assert session is not None
            pending_service_key = session.temp_data.get("service_key")
            pending_target_email = session.temp_data.get("target_email")

            if (
                pending_service_key
                and pending_target_email
                and identity is not None
                and identity.get("role") == "tenant"
            ):
                tenant = await tenants_repository.get_by_owner(db, identity["user_id"])
                if tenant is not None:
                    mailbox = await mailbox_config_repository.get_by_tenant(
                        db, tenant.id
                    )
                    if mailbox is not None and mailbox.status == "connected":
                        job = await mailbox_lookup_repository.create_job(
                            db,
                            tenant_id=tenant.id,
                            mailbox_id=mailbox.id,
                            service_key=pending_service_key,
                            target_email=pending_target_email,
                        )
                        await db.flush()
                        await db.commit()

                        redis_manager = get_redis_manager()
                        try:
                            enqueued = (
                                await enqueue_job(redis_manager, job.id)
                                if redis_manager is not None
                                else False
                            )
                        except Exception:
                            logger.exception(
                                "Failed to enqueue lookup job %s for tenant %s",
                                job.id,
                                tenant.id,
                            )
                            enqueued = False

                        if enqueued:
                            lookup_job_id = str(job.id)
                            tenant_id_out = str(tenant.id)
                            session.temp_data.pop("pending_lookup_intent", None)
                            session.temp_data.pop("service_key", None)
                            session.temp_data.pop("target_email", None)
                            await session_service.save_session(session, touch_ttl=False)
                        else:
                            reply = tenant_console_service._t(
                                tenant_console_service.KEY_CODIGO_ERROR
                            )
                            logger.warning(
                                "Compensating: deleting job %s after enqueue "
                                "failure for tenant %s",
                                job.id,
                                tenant.id,
                            )
                            try:
                                await db.delete(job)
                                await db.commit()
                            except Exception:
                                logger.critical(
                                    "Job %s created but enqueue failed AND "
                                    "compensating delete failed. Marking failed.",
                                    job.id,
                                )
                                try:
                                    await db.rollback()
                                    await mailbox_lookup_repository.transition_status(
                                        db,
                                        job,
                                        "failed",
                                        error_code="queue_unavailable",
                                        error_detail_safe=(
                                            "Queue processing unavailable"
                                        ),
                                    )
                                    await db.commit()
                                except Exception:
                                    logger.exception(
                                        "Failed to mark job %s as failed",
                                        job.id,
                                    )
                    else:
                        reply = tenant_console_service._t(
                            tenant_console_service.KEY_CODIGO_ERROR
                        )
                        logger.warning(
                            "No connected mailbox for tenant %s; keeping lookup intent",
                            tenant.id,
                        )
    except Exception:
        logger.exception("Failed to orchestrate lookup job for phone=%s", phone)
        if (
            session is not None
            and session.temp_data.get("pending_lookup_intent") == "true"
        ):
            reply = tenant_console_service._t(tenant_console_service.KEY_CODIGO_ERROR)

    return WhatsAppConsoleResponse(
        reply=reply,
        lookup_job_id=lookup_job_id,
        tenant_id=tenant_id_out,
    )


# ====================================================================
# Client console handler
# ====================================================================


async def _handle_client_console(
    phone: str,
    message: str,
    instance: str | None,
    manager: object,
    db: AsyncSession,
    identity: dict,
    locale: str = "es",
) -> WhatsAppConsoleResponse:
    """Handle message from identified Client user."""
    session_service = WhatsAppSessionService(
        connection_manager=manager,
        ttl_seconds=settings.whatsapp_session_ttl_minutes * 60,
    )

    facade = WhatsAppClientConsoleFacade(
        session_service=session_service,
        locale=locale,
    )

    exit_cmd = message.strip().lower() in ("0", "salir")

    try:
        reply = await facade.process_message(
            phone=phone,
            message=message,
            identity=identity,
            instance=instance,
            db=db,
        )
    except (RedisUnavailableError, ConnectionError, TimeoutError, OSError):
        return WhatsAppConsoleResponse(reply=CONSOLE_STATE_UNAVAILABLE_REPLY)

    resp = WhatsAppConsoleResponse(reply=reply)
    if exit_cmd:
        resp.status = "closed"
    return resp


# ====================================================================
# Unauthenticated code lookup handler
# ====================================================================


async def _handle_unauthenticated_codigo(
    phone_digits: str,
    message: str,
    sender_lid: str | None,
    manager: object,
    tenant: object,
    db: AsyncSession,
) -> WhatsAppConsoleResponse:
    """Start or continue code lookup for an unregistered WhatsApp identity.

    Called by ``_route_by_instance`` when a sender in a known tenant
    instance is neither a tenant admin nor a registered client.

    The function manages its own multi-step session under
    ``session:unreg:...`` so that subsequent messages continue the
    dialog rather than being treated as fresh requests.
    """
    locale = getattr(tenant, "locale", "es") or "es"
    msg = message.strip()
    session_key = _unauth_session_key(phone_digits, sender_lid)

    session_service = WhatsAppSessionService(
        connection_manager=manager,
        ttl_seconds=settings.whatsapp_session_ttl_minutes * 60,
    )

    session = await session_service.get_session(session_key)

    # ── No active session → only start on codigo keywords ────────
    if session is None:
        if msg.lower() not in ("codigo", "código", "code"):
            return WhatsAppConsoleResponse(
                reply=_i18n_t(locale, "wa.client.access_denied")
            )

        # Check mailbox is configured
        mailbox = await mailbox_config_repository.get_by_tenant(db, tenant.id)
        if mailbox is None or mailbox.status not in ("connected", "error"):
            return WhatsAppConsoleResponse(
                reply=_i18n_t(locale, "wa.tenant.codigo.no_mailbox")
            )

        # Get effective service list
        effective_keys = await code_services_repository.get_effective_service_keys(
            db, tenant.id
        )
        if not effective_keys:
            return WhatsAppConsoleResponse(
                reply=_i18n_t(locale, "wa.tenant.codigo.no_code_services_client")
            )

        # Build service list display
        lines: list[str] = []
        for i, key in enumerate(effective_keys, start=1):
            label = _UNAUTH_CODIGO_SERVICE_LABELS.get(key, key.capitalize())
            lines.append(f"{i}\U0001f53b {label}")
        lines.append("0\U0001f53b " + _i18n_t(locale, "wa.tenant.codigo.cancel_direct"))
        service_list = "\n".join(lines)

        # Create session with flow state
        session = await session_service.create_session(session_key)
        session.flow = _UNAUTH_CODIGO_FLOW
        session.step = _UNAUTH_CODIGO_STEP_SERVICE
        session.temp_data = {"codigo_effective_keys": effective_keys}
        await session_service.save_session(session)

        return WhatsAppConsoleResponse(
            reply=_i18n_t(
                locale, "wa.tenant.codigo.service_prompt", service_list=service_list
            )
        )

    # ── Existing session --- route by step ────────────────────────
    if session.flow != _UNAUTH_CODIGO_FLOW:
        await session_service.clear_session(session_key)
        return WhatsAppConsoleResponse(reply=_i18n_t(locale, "wa.client.access_denied"))

    if session.step == _UNAUTH_CODIGO_STEP_SERVICE:
        return await _handle_unauth_codigo_service(
            msg, session, session_service, session_key, tenant, db, locale
        )

    if session.step == _UNAUTH_CODIGO_STEP_EMAIL:
        return await _handle_unauth_codigo_email(
            msg, session, session_service, session_key, tenant, db, locale, manager
        )

    await session_service.clear_session(session_key)
    return WhatsAppConsoleResponse(reply=_i18n_t(locale, "wa.client.access_denied"))


async def _handle_unauth_codigo_service(
    msg: str,
    session: object,
    session_service: WhatsAppSessionService,
    session_key: str,
    tenant: object,
    db: AsyncSession,
    locale: str,
) -> WhatsAppConsoleResponse:
    """Handle service selection in unauthenticated code lookup."""
    effective_keys = session.temp_data.get("codigo_effective_keys", [])
    if not effective_keys:
        await session_service.clear_session(session_key)
        return WhatsAppConsoleResponse(
            reply=_i18n_t(locale, "wa.tenant.codigo.no_code_services_client")
        )

    try:
        idx = int(msg.strip())
    except ValueError:
        return WhatsAppConsoleResponse(
            reply=_i18n_t(locale, "wa.tenant.codigo.invalid_service")
        )

    if idx < 1 or idx > len(effective_keys):
        if idx == 0:
            await session_service.clear_session(session_key)
            return WhatsAppConsoleResponse(reply=_i18n_t(locale, "wa.tenant.cancelled"))
        return WhatsAppConsoleResponse(
            reply=_i18n_t(locale, "wa.tenant.codigo.invalid_service")
        )

    service_key = effective_keys[idx - 1]
    label = _UNAUTH_CODIGO_SERVICE_LABELS.get(service_key, service_key.capitalize())

    session.temp_data["service_key"] = service_key
    session.temp_data["service_label"] = label
    session.step = _UNAUTH_CODIGO_STEP_EMAIL
    await session_service.save_session(session)

    return WhatsAppConsoleResponse(
        reply=_i18n_t(locale, "wa.tenant.codigo.email_prompt", service_label=label)
    )


async def _handle_unauth_codigo_email(
    msg: str,
    session: object,
    session_service: WhatsAppSessionService,
    session_key: str,
    tenant: object,
    db: AsyncSession,
    locale: str,
    manager: object,
) -> WhatsAppConsoleResponse:
    """Handle email input, create lookup job, and return response with job_id."""
    target_email = msg.strip()
    if (
        not target_email
        or len(target_email) < 3
        or "@" not in target_email
        or "." not in target_email.split("@", 1)[1]
    ):
        return WhatsAppConsoleResponse(
            reply=_i18n_t(locale, "wa.tenant.codigo.invalid_email")
        )

    service_key = session.temp_data.get("service_key")
    if not service_key:
        await session_service.clear_session(session_key)
        return WhatsAppConsoleResponse(reply=_i18n_t(locale, "wa.tenant.cancelled"))

    # Create lookup job
    mailbox = await mailbox_config_repository.get_by_tenant(db, tenant.id)
    if mailbox is None or mailbox.status != "connected":
        return WhatsAppConsoleResponse(
            reply=_i18n_t(locale, "wa.tenant.codigo.no_mailbox")
        )

    lookup_job_id: str | None = None
    tenant_id_out: str | None = None

    try:
        job = await mailbox_lookup_repository.create_job(
            db,
            tenant_id=tenant.id,
            mailbox_id=mailbox.id,
            service_key=service_key,
            target_email=target_email,
        )
        await db.flush()
        await db.commit()

        enqueued = False
        try:
            enqueued = (
                await enqueue_job(manager, job.id) if manager is not None else False
            )
        except Exception:
            logger.exception(
                "Failed to enqueue lookup job %s for tenant %s", job.id, tenant.id
            )

        if enqueued:
            lookup_job_id = str(job.id)
            tenant_id_out = str(tenant.id)
        else:
            try:
                await db.delete(job)
                await db.commit()
            except Exception:
                logger.critical("Failed to delete job %s after enqueue failure", job.id)
            return WhatsAppConsoleResponse(
                reply=_i18n_t(locale, "wa.tenant.codigo.error")
            )
    except Exception:
        logger.exception("Failed to create lookup job for tenant %s", tenant.id)
        return WhatsAppConsoleResponse(reply=_i18n_t(locale, "wa.tenant.codigo.error"))

    # Clear session on success
    try:
        await session_service.clear_session(session_key)
    except Exception:
        pass

    return WhatsAppConsoleResponse(
        reply=_i18n_t(locale, "wa.tenant.codigo.buscando"),
        lookup_job_id=lookup_job_id,
        tenant_id=tenant_id_out,
    )


# ====================================================================
# Client Context Shortcut handler
# ====================================================================


async def _handle_active_client_context(
    phone: str,
    message: str,
    manager: object,
    tenant: object,
    db: AsyncSession,
    instance: str | None,
) -> WhatsAppConsoleResponse | None:
    """Check for active Client Context Shortcut and handle the message.

    Called from ``_route_by_instance`` before routing to the Tenant
    console.  Returns a response when a context session exists and
    the message was handled; returns ``None`` to fall through to
    the regular Tenant console.

    Context sessions are stored under ``wa:client_ctx:{phone}`` with
    a 5-minute TTL.
    """
    import json

    from app.api.v1.endpoints.integrations.console_context_shortcut import (  # noqa: F811
        handle_ctx_active_client_menu,
        handle_ctx_active_deactivate_confirm,
        handle_ctx_active_detail,
        handle_ctx_active_edit_field,
        handle_ctx_active_edit_value,
        handle_ctx_creating_confirm,
        handle_ctx_creating_first,
        handle_ctx_creating_name,
        handle_ctx_creating_password,
        handle_ctx_creating_phone,
        handle_ctx_creating_username,
        handle_ctx_inactive_client_menu,
        handle_ctx_inactive_delete_confirm,
        handle_ctx_inactive_edit_field,
        handle_ctx_inactive_edit_value,
    )

    if not phone:
        return None

    ctx_key = f"wa:client_ctx:{phone}"

    async def _get_ctx(client):
        return await client.get(ctx_key)

    raw = await manager.execute("get_context", _get_ctx)
    if raw is None:
        return None

    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        return None

    if data.get("flow") != "client_shortcut":
        return None

    step = data.get("step", "")
    temp_data = data.get("temp_data", {})
    target_phone = temp_data.get("target_phone", "")
    target_lid = temp_data.get("target_lid", "")
    admin_jid = temp_data.get("admin_jid", "")

    msg_lower = message.strip().lower()

    # ── Helper: save context with optional TTL refresh ────────────
    async def _save_ctx(*, refresh_ttl: bool = True) -> None:
        async def _set(client):
            if refresh_ttl:
                await client.set(ctx_key, json.dumps(data), ex=300)
            else:
                await client.set(ctx_key, json.dumps(data), keepttl=True)

        await manager.execute("set_context", _set)

    # ── Helper: clear context ─────────────────────────────────────
    async def _clear_ctx() -> None:
        async def _del(client):
            await client.delete(ctx_key)

        await manager.execute("clear_context", _del)

    # ── Check if target is a registered client ────────────────────
    target_phone_norm = normalize_phone(target_phone) if target_phone else None

    active_client = None
    if target_phone_norm:
        active_client = await clients_repository.get_active_client_by_tenant_phone(
            db, tenant.id, target_phone_norm
        )
    if active_client is None and target_lid:
        active_client = await clients_repository.get_active_client_by_tenant_lid(
            db, tenant.id, target_lid
        )

    if active_client is not None:
        # Active client — show active client menu within context
        data["step"] = "active_menu"
        data["temp_data"]["client_id"] = str(active_client.id)
        await _save_ctx(refresh_ttl=True)
        return await handle_ctx_active_client_menu(
            msg_lower,
            message,
            data,
            admin_jid,
            active_client,
            tenant,
            db,
            _save_ctx,
            _clear_ctx,
        )

    # ── Check for inactive client ────────────────────────────────
    inactive_client = None
    if target_phone_norm:
        inactive_client = await clients_repository.get_client_by_tenant_phone(
            db, tenant.id, target_phone_norm
        )
    if inactive_client is None and target_lid:
        inactive_client = await clients_repository.get_client_by_tenant_lid(
            db, tenant.id, target_lid
        )

    if inactive_client is not None:
        # Inactive client — show inactive client menu within context
        data["step"] = "inactive_menu"
        data["temp_data"]["client_id"] = str(inactive_client.id)
        await _save_ctx(refresh_ttl=True)
        return await handle_ctx_inactive_client_menu(
            msg_lower,
            message,
            data,
            admin_jid,
            inactive_client,
            tenant,
            db,
            _save_ctx,
            _clear_ctx,
        )

    # ── Handle 0 / cerrar at any step (close context) ─────────────
    if msg_lower in ("0", "salir", "cerrar"):
        await _clear_ctx()
        return WhatsAppConsoleResponse(
            reply="\u274c Contexto cerrado.",
            reply_to=admin_jid,
        )

    # ── Handle by step ────────────────────────────────────────────
    if step == "menu":
        blocked = await client_messaging_block_repository.find_active(
            db,
            tenant.id,
            phone=target_phone_norm if target_phone_norm else None,
            whatsapp_lid=target_lid,
        )

        if blocked:
            return await _handle_ctx_blocked_menu(
                msg_lower,
                data,
                _save_ctx,
                _clear_ctx,
                admin_jid,
                target_phone_norm,
                target_lid,
                tenant,
                db,
            )
        return await _handle_ctx_unblocked_menu(
            msg_lower,
            data,
            _save_ctx,
            _clear_ctx,
            admin_jid,
            target_phone_norm,
            target_lid,
            tenant,
            db,
        )

    # ── Creating flow steps ───────────────────────────────────────
    if step == "creating":
        resp = await handle_ctx_creating_first(data, tenant, db, admin_jid)
        await _save_ctx(refresh_ttl=True)
        return resp

    if step == "creating_phone":
        resp = await handle_ctx_creating_phone(msg_lower, message, data, admin_jid)
        if resp is None:
            await _clear_ctx()
            return WhatsAppConsoleResponse(
                reply="\u274c Creaci\u00f3n cancelada.",
                reply_to=admin_jid,
            )
        await _save_ctx(refresh_ttl=True)
        return resp

    if step == "creating_name":
        resp = await handle_ctx_creating_name(msg_lower, message, data, admin_jid)
        if resp is None:
            await _clear_ctx()
            return WhatsAppConsoleResponse(
                reply="\u274c Creaci\u00f3n cancelada.",
                reply_to=admin_jid,
            )
        await _save_ctx(refresh_ttl=True)
        return resp

    if step == "creating_username":
        resp = await handle_ctx_creating_username(msg_lower, message, data, admin_jid)
        if resp is None:
            await _clear_ctx()
            return WhatsAppConsoleResponse(
                reply="\u274c Creaci\u00f3n cancelada.",
                reply_to=admin_jid,
            )
        await _save_ctx(refresh_ttl=True)
        return resp

    if step == "creating_password":
        resp = await handle_ctx_creating_password(msg_lower, message, data, admin_jid)
        if resp is None:
            await _clear_ctx()
            return WhatsAppConsoleResponse(
                reply="\u274c Creaci\u00f3n cancelada.",
                reply_to=admin_jid,
            )
        await _save_ctx(refresh_ttl=True)
        return resp

    if step == "creating_confirm":
        return await handle_ctx_creating_confirm(
            msg_lower,
            message,
            data,
            admin_jid,
            tenant,
            db,
            target_phone_norm,
            target_lid,
            _clear_ctx,
        )

    # ── Active client menu steps ──────────────────────────────────
    if step == "active_menu":
        return await handle_ctx_active_client_menu(
            msg_lower,
            message,
            data,
            admin_jid,
            active_client,
            tenant,
            db,
            _save_ctx,
            _clear_ctx,
        )

    if step == "active_detail":
        return await handle_ctx_active_detail(
            msg_lower,
            message,
            data,
            admin_jid,
            active_client,
            tenant,
            db,
            _save_ctx,
            _clear_ctx,
        )

    if step == "active_edit_field":
        resp = await handle_ctx_active_edit_field(msg_lower, message, data, admin_jid)
        if resp is not None:
            await _save_ctx(refresh_ttl=True)
            return resp
        return WhatsAppConsoleResponse(
            reply="\u274c Acci\u00f3n cancelada.",
            reply_to=admin_jid,
        )

    if step == "active_edit_value":
        return await handle_ctx_active_edit_value(
            msg_lower, message, data, admin_jid, tenant, db, _clear_ctx
        )

    if step == "active_deactivate_confirm":
        return await handle_ctx_active_deactivate_confirm(
            msg_lower, message, data, admin_jid, tenant, db, _clear_ctx
        )

    # ── Inactive client menu steps ────────────────────────────────
    if step == "inactive_menu":
        return await handle_ctx_inactive_client_menu(
            msg_lower,
            message,
            data,
            admin_jid,
            inactive_client,
            tenant,
            db,
            _save_ctx,
            _clear_ctx,
        )

    if step == "inactive_edit_field":
        resp = await handle_ctx_inactive_edit_field(msg_lower, message, data, admin_jid)
        if resp is not None:
            await _save_ctx(refresh_ttl=True)
            return resp
        return WhatsAppConsoleResponse(
            reply="\u274c Acci\u00f3n cancelada.",
            reply_to=admin_jid,
        )

    if step == "inactive_edit_value":
        return await handle_ctx_inactive_edit_value(
            msg_lower, message, data, admin_jid, tenant, db, _clear_ctx
        )

    if step == "inactive_delete_confirm":
        return await handle_ctx_inactive_delete_confirm(
            msg_lower, message, data, admin_jid, tenant, db, _clear_ctx
        )

    # Unknown step — clear context and fall through
    await _clear_ctx()
    return None


async def _handle_ctx_unblocked_menu(
    msg_lower: str,
    data: dict,
    save_ctx,
    clear_ctx,
    admin_jid: str | None,
    target_phone: str | None,
    target_lid: str | None,
    tenant: object,
    db: AsyncSession,
) -> WhatsAppConsoleResponse:
    """Handle a message in the unblocked unregistered target menu."""

    if msg_lower == "1":
        # Crear cliente — advance to creating step (multi-step flow)
        data["step"] = "creating"
        await save_ctx(refresh_ttl=True)
        return WhatsAppConsoleResponse(
            reply="Iniciando creacion de cliente...",
            reply_to=admin_jid,
        )

    if msg_lower == "2":
        # Bloquear mensajes — create block immediately without confirmation
        await client_messaging_block_repository.create(
            db,
            tenant_id=tenant.id,
            phone=target_phone,
            whatsapp_lid=target_lid,
        )
        await db.commit()
        await clear_ctx()
        return WhatsAppConsoleResponse(
            reply="\u2705 Mensajes bloqueados para este contacto.",
            reply_to=admin_jid,
        )

    if msg_lower in ("0", "salir", "cerrar"):
        await clear_ctx()
        return WhatsAppConsoleResponse(
            reply="\u274c Contexto cerrado.",
            reply_to=admin_jid,
        )

    # Invalid input — do NOT refresh TTL
    await save_ctx(refresh_ttl=False)
    return WhatsAppConsoleResponse(
        reply="\u26a0\ufe0f Opci\u00f3n no v\u00e1lida.\n\n"
        "1\ufe0f\u20e3 Crear cliente\n"
        "2\ufe0f\u20e3 Bloquear mensajes\n"
        "0\ufe0f\u20e3 Cancelar",
        reply_to=admin_jid,
    )


async def _handle_ctx_blocked_menu(
    msg_lower: str,
    data: dict,
    save_ctx,
    clear_ctx,
    admin_jid: str | None,
    target_phone: str | None,
    target_lid: str | None,
    tenant: object,
    db: AsyncSession,
) -> WhatsAppConsoleResponse:
    """Handle a message in the blocked target menu."""

    if msg_lower == "1":
        # Desbloquear mensajes — find active block and unblock
        blocked = await client_messaging_block_repository.find_active(
            db,
            tenant.id,
            phone=target_phone,
            whatsapp_lid=target_lid,
        )
        if blocked is not None:
            await client_messaging_block_repository.unblock(
                db,
                tenant_id=tenant.id,
                block_id=blocked.id,
            )
            await db.commit()
        await clear_ctx()
        return WhatsAppConsoleResponse(
            reply="\u2705 Mensajes desbloqueados para este contacto.",
            reply_to=admin_jid,
        )

    if msg_lower in ("0", "salir", "cerrar"):
        await clear_ctx()
        return WhatsAppConsoleResponse(
            reply="\u274c Contexto cerrado.",
            reply_to=admin_jid,
        )

    # Invalid input — do NOT refresh TTL
    await save_ctx(refresh_ttl=False)
    return WhatsAppConsoleResponse(
        reply="\u26a0\ufe0f Opci\u00f3n no v\u00e1lida.\n\n"
        "1\ufe0f\u20e3 Desbloquear mensajes\n"
        "0\ufe0f\u20e3 Cancelar",
        reply_to=admin_jid,
    )
