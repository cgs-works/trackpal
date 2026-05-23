from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import ApiKeyDbDep
from app.core.config import settings
from app.core.phone import normalize_phone
from app.core.redis_client import RedisUnavailableError, get_redis_manager
from app.schemas.auth import IdentifyResponse
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

# ---------------------------------------------------------------------------
# Role-based routing reply templates (Spanish)
# ---------------------------------------------------------------------------

UNKNOWN_PHONE_REPLY = (
    "❌ No tienes acceso a la consola. "
    "El número de teléfono no está registrado en el sistema."
)

TENANT_CONSOLE_PLACEHOLDER = (
    "🤖 *Trackpal Consola de Administración*\n\n"
    "Bienvenido a la consola de administración para tu tenant.\n\n"
    "Esta funcionalidad estará disponible próximamente."
)


class _TenantConsoleItem:
    """Wraps a tenant ORM object for the simple
    attribute-based interface expected by WhatsAppConsoleService."""

    def __init__(self, profile) -> None:
        self.id = profile.id
        self.full_name = profile.full_name
        self.is_active = profile.is_active
        self.email = profile.email
        self.phone = profile.phone
        owner = getattr(profile, "owner", None) or getattr(profile, "user", None)
        self.username = owner.username if owner else ""
        self.evolution_instance_name = profile.evolution_instance_name
        self.created_at = profile.created_at


class _TenantConsoleAdapter:
    """Adapts ``TenantService`` + ``db`` to the simple
    ``get_tenants()`` / ``get_tenant(id)`` interface
    expected by ``WhatsAppConsoleService``."""

    def __init__(self, tenant_service: TenantService, db: AsyncSession) -> None:
        self._service = tenant_service
        self._db = db

    async def get_tenants(self) -> list[_TenantConsoleItem]:
        profiles, _ = await self._service.get_tenants(self._db)
        return [_TenantConsoleItem(p) for p in profiles]

    async def get_tenant(self, tenant_id: str) -> _TenantConsoleItem | None:
        from uuid import UUID

        profile = await self._service.get_tenant(self._db, UUID(tenant_id))
        if profile is None:
            return None
        return _TenantConsoleItem(profile)

    async def get_tenant_by_username(self, username: str) -> _TenantConsoleItem | None:
        """Return a single tenant whose username matches, or None."""
        from app.crud import users as user_crud

        user = await user_crud.get_by_username(self._db, username)
        if user is None or user.role != "tenant":
            return None
        return await self.get_tenant(str(user.id))

    async def create_tenant(self, payload: dict) -> dict:
        """Create a tenant from a WhatsApp-guided payload dict.

        Returns a dict with:
            success (bool): True on success.
            tenant (optional): Created tenant info on success.
            auto_password (optional): Auto-generated password.
            error (str): Error message on failure.
        """
        from app.schemas.tenant import TenantCreate

        try:
            create_payload = TenantCreate(**payload)
        except Exception as exc:
            return {"success": False, "error": str(exc)}

        try:
            profile, auto_password = await self._service.create_tenant(
                self._db, create_payload
            )
            return {
                "success": True,
                "tenant": _TenantConsoleItem(profile),
                "auto_password": auto_password,
            }
        except ValueError as exc:
            return {"success": False, "error": str(exc)}

    async def activate_tenant(self, tenant_id: str) -> dict:
        try:
            profile = await self._service.activate_tenant(self._db, UUID(tenant_id))
            if profile is None:
                return {"success": False, "error": "Tenant not found"}
            return {"success": True, "tenant": _TenantConsoleItem(profile)}
        except ValueError as exc:
            return {"success": False, "error": str(exc)}

    async def deactivate_tenant(self, tenant_id: str) -> dict:
        try:
            profile = await self._service.deactivate_tenant(self._db, UUID(tenant_id))
            if profile is None:
                return {"success": False, "error": "Tenant not found"}
            return {"success": True, "tenant": _TenantConsoleItem(profile)}
        except ValueError as exc:
            return {"success": False, "error": str(exc)}

    async def delete_tenant(self, tenant_id: str) -> dict:
        try:
            deleted = await self._service.delete_tenant(self._db, UUID(tenant_id))
            if not deleted:
                return {"success": False, "error": "Tenant not found"}
            return {"success": True}
        except ValueError as exc:
            return {"success": False, "error": str(exc)}

    async def update_tenant(self, tenant_id: str, payload: dict) -> dict:
        """Update a tenant from a WhatsApp-guided update payload dict.

        Returns a dict with:
            success (bool): True on success.
            tenant (optional): Updated tenant info on success.
            error (str): Error message on failure.
        """
        from app.schemas.tenant import TenantUpdate

        try:
            update_payload = TenantUpdate(**payload)
        except Exception as exc:
            return {"success": False, "error": str(exc)}

        try:
            profile = await self._service.update_tenant(
                self._db, UUID(tenant_id), update_payload
            )
            if profile is None:
                return {"success": False, "error": "Tenant not found"}
            return {"success": True, "tenant": _TenantConsoleItem(profile)}
        except ValueError as exc:
            return {"success": False, "error": str(exc)}


router = APIRouter(prefix="/integrations", tags=["integrations"])
auth_service = AuthService()
console_service = WhatsAppConsoleService()
tenant_service = TenantService()

CONSOLE_STATE_UNAVAILABLE_REPLY = ContingencyReplyPolicy.TEMPORARY_UNAVAILABLE


@router.get("/n8n/identify", response_model=IdentifyResponse)
async def identify_n8n(
    phone: str,
    db: ApiKeyDbDep,
):
    result = await auth_service.identify_by_phone(db, phone)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found or deactivated",
        )
    return result


@router.post("/n8n/console", response_model=WhatsAppConsoleResponse)
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
