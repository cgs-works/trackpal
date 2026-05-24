from fastapi import APIRouter
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import ApiKeyDbDep
from app.core.config import settings
from app.core.phone import normalize_phone
from app.core.redis_client import RedisUnavailableError, get_redis_manager
from app.schemas.whatsapp import WhatsAppConsoleRequest, WhatsAppConsoleResponse
from app.services.auth_service import AuthService
from app.services.catalog_service import CatalogService
from app.services.client_service import ClientService
from app.services.contingency_reply_policy import ContingencyReplyPolicy
from app.services.profile_service import ProfileService
from app.services.subscription_service import SubscriptionService
from app.services.tenant_service import TenantService
from app.services.whatsapp_auth_session_service import WhatsAppAuthSessionService
from app.services.whatsapp_console_service import WhatsAppConsoleService
from app.services.whatsapp_master_console_facade import WhatsAppMasterConsoleFacade
from app.services.whatsapp_session_service import WhatsAppSessionService
from app.services.whatsapp_tenant_console_facade import WhatsAppTenantConsoleFacade
from app.services.whatsapp_tenant_console_service import WhatsAppTenantConsoleService
from app.api.v1.endpoints.integrations.adapter import (
    _TenantConsoleAdapter,
    UNKNOWN_PHONE_REPLY,
)

console_router = APIRouter(tags=["integrations"])
auth_service = AuthService()
console_service = WhatsAppConsoleService()
tenant_service = TenantService()

CONSOLE_STATE_UNAVAILABLE_REPLY = ContingencyReplyPolicy.TEMPORARY_UNAVAILABLE


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

    # Create Redis-dependent services when available
    manager = get_redis_manager()
    if manager is None:
        return WhatsAppConsoleResponse(reply=CONSOLE_STATE_UNAVAILABLE_REPLY)

    # Identify caller by phone and route by role
    identity = await auth_service.identify_by_phone(db, phone)

    if identity is None:
        return WhatsAppConsoleResponse(reply=UNKNOWN_PHONE_REPLY)

    role = identity["role"]

    if role == "master":
        return await _handle_master_console(
            phone=phone,
            message=request.message,
            instance=request.instance,
            manager=manager,
            db=db,
        )

    if role == "tenant":
        return await _handle_tenant_console(
            phone=phone,
            message=request.message,
            instance=request.instance,
            manager=manager,
            db=db,
        )

    # Unknown role — treat as no-access
    return WhatsAppConsoleResponse(reply=UNKNOWN_PHONE_REPLY)


async def _handle_master_console(
    phone: str,
    message: str,
    instance: str | None,
    manager: object,
    db: AsyncSession,
) -> WhatsAppConsoleResponse:
    """Handle a message from an identified Master user.

    Builds Redis-dependent services, creates the Master Console facade,
    and processes the message.  This is the extracted inline path from
    the original ``whatsapp_console`` endpoint — behavior is preserved.
    """
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

    # Create tenant adapter for console service
    adapter = _TenantConsoleAdapter(tenant_service, db)

    # Create facade orchestrator
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


async def _handle_tenant_console(
    phone: str,
    message: str,
    instance: str | None,
    manager: object,
    db: AsyncSession,
) -> WhatsAppConsoleResponse:
    """Handle a message from an identified Tenant Admin user.

    Builds Redis-dependent services, the Tenant console service,
    and the facade orchestrator, then processes the message.
    Redis failures return the relayable unavailable reply.
    """
    # Create tenant-scoped services
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

    return WhatsAppConsoleResponse(reply=reply)
