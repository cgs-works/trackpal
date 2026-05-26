"""WhatsApp console entrypoint for n8n transport with instance-first routing.

Instance-first routing resolution order:
1. If ``instance == MASTER_WHATSAPP_INSTANCE`` → only master flow.
2. If instance is a tenant instance → resolve tenant, then identity
   within that tenant (admin by ``tenant.whatsapp_phone``, client by
   ``(tenant_id, phone)``).
3. If both tenant admin and client match → prompt for mode and persist
   in Redis until ``0`` or ``/menu``.
"""

import logging

from fastapi import APIRouter
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import ApiKeyDbDep
from app.api.v1.endpoints.integrations.adapter import UNKNOWN_PHONE_REPLY
from app.api.v1.endpoints.integrations.console_handlers import (
    _handle_client_console,
    _handle_master_console,
    _handle_tenant_console,
)
from app.api.v1.endpoints.integrations.console_modes import _handle_ambiguity
from app.core.config import settings
from app.core.database import set_internal_rls_context
from app.core.i18n import t
from app.core.phone import normalize_phone
from app.core.redis_client import get_redis_manager
from app.repositories import clients_repository, tenants_repository
from app.schemas.whatsapp import WhatsAppConsoleRequest, WhatsAppConsoleResponse
from app.services.auth_service import AuthService
from app.services.contingency_reply_policy import ContingencyReplyPolicy

logger = logging.getLogger(__name__)


def _tl(tenant: object) -> str:
    """Resolve locale from tenant, defaulting to ``\"es\"``."""
    return getattr(tenant, "locale", "es") or "es"


console_router = APIRouter(tags=["integrations"])
auth_service = AuthService()
CONSOLE_STATE_UNAVAILABLE_REPLY = ContingencyReplyPolicy.TEMPORARY_UNAVAILABLE


# ====================================================================
# Main endpoint
# ====================================================================


@console_router.post("/n8n/console", response_model=WhatsAppConsoleResponse)
async def whatsapp_console(
    request: WhatsAppConsoleRequest,
    db: ApiKeyDbDep,
):
    """Entrypoint for n8n transport: receive message, return reply.

    n8n calls this endpoint with the normalised phone, message, and
    optional Evolution instance. The backend identifies the caller,
    runs the console flow logic, and returns the reply text that n8n
    relays through Evolution API.
    """
    phone = normalize_phone(request.phone) or ""

    manager = get_redis_manager()
    if manager is None:
        return WhatsAppConsoleResponse(reply=CONSOLE_STATE_UNAVAILABLE_REPLY)

    instance = request.instance
    if instance:
        return await _route_by_instance(
            phone=phone,
            message=request.message,
            instance=instance,
            manager=manager,
            db=db,
        )

    # Legacy phone-only identification (no instance provided)
    identity = await auth_service.identify_by_phone(db, phone)
    if identity is None:
        return WhatsAppConsoleResponse(reply=UNKNOWN_PHONE_REPLY)

    role = identity["role"]
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


# ====================================================================
# Instance-first routing
# ====================================================================


async def _route_by_instance(
    phone: str,
    message: str,
    instance: str,
    manager: object,
    db: AsyncSession,
) -> WhatsAppConsoleResponse:
    """Route by Evolution instance first.

    Master instance → only master flow.
    Tenant instance → resolve identity within tenant, handle ambiguity.
    """
    master_instance = settings.master_whatsapp_instance

    # 1. Master instance — only master flow
    if master_instance and instance == master_instance:
        identity = await auth_service.identify_by_phone(db, phone)
        if identity and identity["role"] == "master":
            return await _handle_master_console(
                phone=phone, message=message, instance=instance,
                manager=manager, db=db,
            )
        return WhatsAppConsoleResponse(reply=UNKNOWN_PHONE_REPLY)

    # 2. Tenant instance — resolve tenant
    await set_internal_rls_context(db)
    tenant = await tenants_repository.get_by_instance(db, instance)
    if tenant is None:
        # Unknown instance — fall back to legacy phone-based identification
        identity = await auth_service.identify_by_phone(db, phone)
        if identity is None:
            return WhatsAppConsoleResponse(reply=UNKNOWN_PHONE_REPLY)
        role = identity["role"]
        if role == "master":
            return await _handle_master_console(
                phone=phone, message=message, instance=instance,
                manager=manager, db=db,
            )
        if role == "tenant":
            return await _handle_tenant_console(
                phone=phone, message=message, instance=instance,
                manager=manager, db=db,
            )
        return WhatsAppConsoleResponse(reply=UNKNOWN_PHONE_REPLY)

    if not tenant.is_active:
        return WhatsAppConsoleResponse(reply=t(_tl(tenant), "wa.client.access_denied"))

    # 3. Resolve identity within tenant
    phone_digits = normalize_phone(phone) or phone

    # Check tenant admin
    tenant_admin = None
    if tenant.whatsapp_phone:
        admin_phone = normalize_phone(tenant.whatsapp_phone)
        if admin_phone == phone_digits:
            tenant_admin = tenant

    # Check client within tenant — handle legacy duplicates safely
    try:
        client = await clients_repository.get_active_client_by_tenant_phone(
            db, tenant.id, phone_digits
        )
    except Exception:
        logger.exception(
            "Duplicate client phone detected for tenant=%s phone=%s",
            tenant.id, phone_digits,
        )
        return WhatsAppConsoleResponse(
            reply=t(_tl(tenant), "wa.client.multiple_matches")
        )

    has_tenant_admin = tenant_admin is not None
    has_client = client is not None

    # 4. Handle ambiguity or direct match
    if has_tenant_admin and has_client:
        return await _handle_ambiguity(
            phone=phone_digits, message=message, instance=instance,
            manager=manager, db=db, tenant=tenant, client=client,
        )

    if has_tenant_admin:
        return await _handle_tenant_console(
            phone=phone, message=message, instance=instance,
            manager=manager, db=db,
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
            phone=phone, message=message, instance=instance,
            manager=manager, db=db,
            identity=client_identity, locale=client_locale,
        )

    return WhatsAppConsoleResponse(reply=t(_tl(tenant), "wa.client.access_denied"))
