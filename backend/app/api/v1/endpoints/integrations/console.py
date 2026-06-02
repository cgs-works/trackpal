"""WhatsApp console entrypoint for n8n transport with instance-first routing."""

import logging

from fastapi import APIRouter
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import ApiKeyDbDep
from app.api.v1.endpoints.integrations.adapter import UNKNOWN_PHONE_REPLY
from app.api.v1.endpoints.integrations.console_handlers import (
    _handle_active_client_context,
    _handle_client_console,
    _handle_master_console,
    _handle_tenant_console,
    _handle_unauthenticated_codigo,
)
from app.api.v1.endpoints.integrations.console_modes import _handle_ambiguity
from app.core.config import settings
from app.core.database import set_internal_rls_context
from app.core.i18n import t
from app.core.phone import normalize_phone
from app.core.redis_client import RedisConnectionManager, get_redis_manager
from app.models import Tenant
from app.repositories import (
    blocked_clients_repository,
    clients_repository,
    tenants_repository,
    users_repository,
)
from app.schemas.whatsapp import WhatsAppConsoleRequest, WhatsAppConsoleResponse
from app.services.auth_service import AuthService
from app.services.contingency_reply_policy import ContingencyReplyPolicy
from app.services.whatsapp_session_service import WhatsAppSessionService

logger = logging.getLogger(__name__)


def _tl(tenant: object) -> str:
    return getattr(tenant, "locale", "es") or "es"


def _jid_phone(jid: str | None) -> str | None:
    """Extract a normalized phone from a WhatsApp phone JID.

    Evolution may include device suffixes such as
    ``12015550002:12@s.whatsapp.net``. Treat those as same phone when
    deciding whether a from_me target is the tenant admin's own chat.
    """
    if not jid or "@s.whatsapp.net" not in jid:
        return None
    local = jid.split("@", 1)[0].split(":", 1)[0]
    return normalize_phone(local)


console_router = APIRouter(tags=["integrations"])
auth_service = AuthService()
CONSOLE_STATE_UNAVAILABLE_REPLY = ContingencyReplyPolicy.TEMPORARY_UNAVAILABLE


@console_router.post("/n8n/console", response_model=WhatsAppConsoleResponse)
async def whatsapp_console(
    request: WhatsAppConsoleRequest,
    db: ApiKeyDbDep,
):
    phone = normalize_phone(request.phone) or ""
    sender_lid = request.sender_lid

    manager = get_redis_manager()
    if manager is None:
        return WhatsAppConsoleResponse(reply=CONSOLE_STATE_UNAVAILABLE_REPLY)

    instance = request.instance
    if instance:
        return await _route_by_instance(
            phone=phone,
            message=request.message,
            instance=instance,
            sender_lid=sender_lid,
            manager=manager,
            db=db,
            from_me=bool(request.from_me),
            admin_phone=request.admin_phone,
            admin_jid=request.admin_jid,
            target_jid=request.target_jid,
            target_phone=request.target_phone,
            target_lid=request.target_lid,
        )

    # Legacy phone-only identification (no instance provided)
    # Fall back to LID when phone is empty
    identity = None
    if phone:
        identity = await auth_service.identify_by_phone(db, phone)
    if identity is None and sender_lid:
        identity = await auth_service.identify_by_lid(db, sender_lid)

    if identity is None:
        return WhatsAppConsoleResponse(reply=UNKNOWN_PHONE_REPLY)

    role = identity["role"]
    if phone and sender_lid and role == "master":
        await users_repository.update_master_lid(db, identity["user_id"], sender_lid)
    if role == "master":
        return await _handle_master_console(
            phone=phone,
            message=request.message,
            instance=instance,
            manager=manager,
            db=db,
        )
    if role == "tenant":
        return await _handle_tenant_console(
            phone=phone,
            message=request.message,
            instance=instance,
            manager=manager,
            db=db,
        )
    return WhatsAppConsoleResponse(reply=UNKNOWN_PHONE_REPLY)


async def _route_by_instance(
    phone: str,
    message: str,
    instance: str,
    sender_lid: str | None,
    manager: RedisConnectionManager,
    db: AsyncSession,
    from_me: bool = False,
    admin_phone: str | None = None,
    admin_jid: str | None = None,
    target_jid: str | None = None,
    target_phone: str | None = None,
    target_lid: str | None = None,
) -> WhatsAppConsoleResponse:
    master_instance = settings.master_whatsapp_instance

    if master_instance and instance == master_instance:
        identity = None
        if phone:
            identity = await auth_service.identify_by_phone(db, phone)
        if identity is None and sender_lid:
            identity = await auth_service.identify_by_lid(db, sender_lid)
        if identity and identity["role"] == "master":
            if phone and sender_lid:
                await users_repository.update_master_lid(
                    db, identity["user_id"], sender_lid
                )
            return await _handle_master_console(
                phone=phone,
                message=message,
                instance=instance,
                manager=manager,
                db=db,
            )
        return WhatsAppConsoleResponse(reply=UNKNOWN_PHONE_REPLY)

    await set_internal_rls_context(db)
    tenant = await tenants_repository.get_by_instance(db, instance)
    if tenant is None:
        # Unknown instance — deny access (no fallback by phone/LID)
        return WhatsAppConsoleResponse(reply=UNKNOWN_PHONE_REPLY)

    if not tenant.is_active:
        return WhatsAppConsoleResponse(reply=t(_tl(tenant), "wa.client.access_denied"))

    # ── from_me contextual routing ────────────────────────────────
    if from_me:
        return await _handle_from_me_routing(
            message=message,
            instance=instance,
            admin_phone=admin_phone,
            admin_jid=admin_jid,
            target_jid=target_jid,
            target_phone=target_phone,
            target_lid=target_lid,
            manager=manager,
            tenant=tenant,
            db=db,
        )

    phone_digits = normalize_phone(phone) or phone

    tenant_admin = None
    if tenant.whatsapp_phone and phone:
        admin_phone = normalize_phone(tenant.whatsapp_phone)
        if admin_phone == phone_digits:
            tenant_admin = tenant
    if tenant_admin is None and sender_lid and tenant.whatsapp_lid == sender_lid:
        tenant_admin = tenant

    client = None
    if phone:
        try:
            client = await clients_repository.get_active_client_by_tenant_phone(
                db, tenant.id, phone_digits
            )
        except Exception:
            logger.exception(
                "Duplicate client phone detected for tenant=%s phone=%s",
                tenant.id,
                phone_digits,
            )
            return WhatsAppConsoleResponse(
                reply=t(_tl(tenant), "wa.client.multiple_matches")
            )

    if client is None and sender_lid:
        client = await clients_repository.get_active_client_by_tenant_lid(
            db, tenant.id, sender_lid
        )

    has_tenant_admin = tenant_admin is not None
    has_client = client is not None

    if phone and sender_lid:
        if tenant_admin and not tenant.whatsapp_lid:
            await tenants_repository.update_tenant_lid(db, tenant.id, sender_lid)
        if client and not client.whatsapp_lid:
            await clients_repository.update_client_lid(db, client.id, sender_lid)

    if has_tenant_admin and has_client:
        return await _handle_ambiguity(
            phone=phone_digits,
            message=message,
            instance=instance,
            manager=manager,
            db=db,
            tenant=tenant,
            client=client,
        )

    if has_tenant_admin:
        # Check for active Client Context Shortcut
        ctx_response = await _handle_active_client_context(
            phone=phone_digits,
            message=message,
            manager=manager,
            tenant=tenant,
            db=db,
            instance=instance,
        )
        if ctx_response is not None:
            return ctx_response
        return await _handle_tenant_console(
            phone=phone,
            message=message,
            instance=instance,
            manager=manager,
            db=db,
        )

    if has_client:
        client_locale = _tl(tenant)
        client_identity = {
            "user_id": str(client.owner_user_id),
            "role": "client",
            "username": client.username,
            "client_id": str(client.id),
            "tenant_id": str(tenant.id),
        }
        return await _handle_client_console(
            phone=phone,
            message=message,
            instance=instance,
            manager=manager,
            db=db,
            identity=client_identity,
            locale=client_locale,
        )

    # ── Unregistered identity in a known tenant instance ────────────
    # Route to code lookup for ``codigo`` keywords, or
    # return silent ``no_reply`` when the sender is blocked.

    from app.api.v1.endpoints.integrations.console_handlers import (
        _unauth_session_key,
    )

    msg_lower = message.strip().lower()

    # Block check first — blocked senders always get silent treatment,
    # even when they already have an active ``codigo`` session. The block
    # check must run before any session-resume path so a block applied
    # mid-flow can no longer be bypassed by continuing the dialog.
    blocked = await blocked_clients_repository.find_active(
        db,
        tenant.id,
        phone=phone_digits if phone_digits else None,
        whatsapp_lid=sender_lid,
    )
    if blocked:
        return WhatsAppConsoleResponse(reply="", no_reply=True)

    # Resume any existing unauthenticated codigo session first so the
    # multi-step dialog can continue across messages.
    if msg_lower not in ("codigo", "código", "code"):
        unauth_key = _unauth_session_key(phone_digits, sender_lid)
        session_service = WhatsAppSessionService(
            connection_manager=manager,
            ttl_seconds=settings.whatsapp_session_ttl_minutes * 60,
        )
        existing = await session_service.get_session(unauth_key)
        if existing and existing.flow == "codigo":
            return await _handle_unauthenticated_codigo(
                phone_digits, message, sender_lid, manager, tenant, db
            )

    # Only "codigo"/"código"/"code" triggers unauthenticated code lookup
    if msg_lower in ("codigo", "código", "code"):
        return await _handle_unauthenticated_codigo(
            phone_digits, message, sender_lid, manager, tenant, db
        )

    return WhatsAppConsoleResponse(reply=t(_tl(tenant), "wa.client.access_denied"))


async def _handle_from_me_routing(
    message: str,
    instance: str,
    admin_phone: str | None,
    admin_jid: str | None,
    target_jid: str | None,
    target_phone: str | None,
    target_lid: str | None,
    manager: RedisConnectionManager,
    tenant: Tenant,
    db: AsyncSession,
) -> WhatsAppConsoleResponse:
    """Route a ``from_me=true`` outgoing trigger.

    Called by ``_route_by_instance`` after resolving the tenant but
    before the regular admin/client identity checks.

    When the target equals the admin's own chat, the message is treated
    as a normal admin message and routed to the standard Tenant console.

    When the target differs from the admin's chat, a client context
    shortcut is started with a 5-minute TTL session.  If a context
    session already exists for this admin, the new trigger is rejected
    silently via ``no_reply=true`` and ``reply_to=<admin_jid>``.
    """
    # ── Step 1: Resolve admin identity ────────────────────────────
    resolved_admin_phone = normalize_phone(admin_phone) if admin_phone else None
    if not resolved_admin_phone:
        # Fall back to tenant's whatsapp_phone
        if tenant.whatsapp_phone:
            resolved_admin_phone = normalize_phone(tenant.whatsapp_phone)
        else:
            # Cannot identify admin — no further routing possible
            return WhatsAppConsoleResponse(reply="", no_reply=True)

    assert resolved_admin_phone is not None  # guaranteed by fallback check above

    # ── Step 2: Determine target identity ─────────────────────────
    target_phone_norm = normalize_phone(target_phone) if target_phone else None
    target_jid_phone = _jid_phone(target_jid)
    admin_jid_phone = _jid_phone(admin_jid)

    # ── Step 3: Check if target == admin (self-target) ────────────
    # Compare normalized phone identities from explicit target_phone
    # and from JIDs. Exact JID equality alone is too brittle because
    # Evolution can include device suffixes in from_me events.
    target_candidates = (target_phone_norm, target_jid_phone)
    admin_candidates = (resolved_admin_phone, admin_jid_phone)
    is_self_target = any(
        target and admin and target == admin
        for target in target_candidates
        for admin in admin_candidates
    ) or (admin_jid and target_jid and admin_jid == target_jid)

    if is_self_target:
        # Route to standard Tenant console
        return await _handle_tenant_console(
            phone=resolved_admin_phone,
            message=message,
            instance=instance,
            manager=manager,
            db=db,
        )

    # ── Step 4: Check for existing active context ─────────────────
    ctx_key = f"wa:client_ctx:{resolved_admin_phone}"

    async def _get_ctx(client):
        return await client.get(ctx_key)

    async def _del_ctx(client):
        await client.delete(ctx_key)
        await client.delete(f"session:admin:{resolved_admin_phone}")

    existing_raw = await manager.execute("get_context", _get_ctx)
    if existing_raw:
        # Existing context. If the admin's own message is "0"/"salir"/"cerrar"
        # from their private chat, close the context cleanly so future
        # /menu triggers don't collide.
        if message.strip().lower() in ("0", "salir", "cerrar"):
            await manager.execute("clear_context", _del_ctx)
            locale = getattr(tenant, "locale", "es") or "es"
            return WhatsAppConsoleResponse(
                reply=t(locale, "wa.tenant.client_context.closed"),
                status="closed",
                reply_to=admin_jid,
                close_jid=admin_jid,
            )
        # Otherwise, reject silently (collision)
        return WhatsAppConsoleResponse(reply="", no_reply=True, reply_to=admin_jid)

    # ── Step 5: Render real contextual menu ───────────────────────
    from app.api.v1.endpoints.integrations.console_context_shortcut import (
        render_initial_context_menu,
    )
    from app.services.whatsapp_session_service import ConversationSession

    reply, context_meta = await render_initial_context_menu(
        db=db,
        tenant=tenant,
        target_phone=target_phone_norm or target_phone,
        target_lid=target_lid,
        target_jid=target_jid,
    )

    session = ConversationSession(
        phone=resolved_admin_phone,
        flow="client_shortcut",
        step="menu",
        temp_data={
            "tenant_id": str(tenant.id),
            "target_phone": target_phone_norm or target_phone,
            "target_lid": target_lid,
            "target_jid": target_jid,
            "admin_jid": admin_jid,
            **context_meta,
        },
    )

    async def _set_ctx(client):
        await client.set(ctx_key, session.model_dump_json(), ex=300)

    await manager.execute("set_context", _set_ctx)

    # ── Step 6: Return contextual response with reply_to and close_jid ─
    # close_jid tells n8n which chat to close when the admin sends
    # "0"/"salir"/"cerrar" in the client-shortcut flow.
    return WhatsAppConsoleResponse(
        reply=reply, reply_to=admin_jid, close_jid=admin_jid
    )
