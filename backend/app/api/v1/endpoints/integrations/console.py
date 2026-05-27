"""WhatsApp console entrypoint for n8n transport with instance-first routing."""

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
from app.repositories import clients_repository, tenants_repository, users_repository
from app.schemas.whatsapp import WhatsAppConsoleRequest, WhatsAppConsoleResponse
from app.services.auth_service import AuthService
from app.services.contingency_reply_policy import ContingencyReplyPolicy

logger = logging.getLogger(__name__)


def _tl(tenant: object) -> str:
    return getattr(tenant, "locale", "es") or "es"


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
    manager: object,
    db: AsyncSession,
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
        # Unknown instance — fall back to legacy phone/LID identification
        identity = None
        if phone:
            identity = await auth_service.identify_by_phone(db, phone)
        if identity is None and sender_lid:
            identity = await auth_service.identify_by_lid(db, sender_lid)
        if identity is None:
            return WhatsAppConsoleResponse(reply=UNKNOWN_PHONE_REPLY)
        role = identity["role"]
        if role == "master":
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
        if role == "tenant":
            return await _handle_tenant_console(
                phone=phone,
                message=message,
                instance=instance,
                manager=manager,
                db=db,
            )
        return WhatsAppConsoleResponse(reply=UNKNOWN_PHONE_REPLY)

    if not tenant.is_active:
        return WhatsAppConsoleResponse(reply=t(_tl(tenant), "wa.client.access_denied"))

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

    return WhatsAppConsoleResponse(reply=t(_tl(tenant), "wa.client.access_denied"))
