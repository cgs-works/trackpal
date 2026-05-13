from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.phone import normalize_phone
from app.core.redis_client import get_redis_manager
from app.core.security import verify_n8n_api_key
from app.schemas.auth import IdentifyResponse
from app.schemas.whatsapp import WhatsAppConsoleRequest, WhatsAppConsoleResponse
from app.services.auth_service import AuthService
from app.services.contingency_reply_policy import ContingencyReplyPolicy
from app.services.tenant_service import TenantService
from app.services.whatsapp_console_service import WhatsAppConsoleService
from app.services.whatsapp_session_service import WhatsAppSessionService


class _TenantConsoleItem:
    """Wraps a TenantProfile ORM object for the simple
    attribute-based interface expected by WhatsAppConsoleService."""

    def __init__(self, profile) -> None:
        self.id = profile.id
        self.full_name = profile.full_name
        self.is_active = profile.is_active
        self.email = profile.email
        self.phone = profile.phone
        self.username = profile.user.username if profile.user else ""
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
DbDep = Annotated[AsyncSession, Depends(get_db)]

CONSOLE_STATE_UNAVAILABLE_REPLY = ContingencyReplyPolicy.TEMPORARY_UNAVAILABLE


@router.get("/n8n/identify", response_model=IdentifyResponse)
async def identify_n8n(
    phone: str,
    x_api_key: Annotated[str, Header(alias="X-API-Key")],
    db: DbDep,
):
    if not verify_n8n_api_key(x_api_key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API Key",
        )
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
    db: DbDep,
    x_api_key: Annotated[str | None, Header(alias="X-API-Key")] = None,
):
    """Entrypoint for n8n transport: receive message, return reply.

    n8n calls this endpoint with the normalised phone, message, and
    optional Evolution instance. The backend identifies the caller,
    runs the console flow logic, and returns the reply text that n8n
    relays through Evolution API.
    """
    if not verify_n8n_api_key(x_api_key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API Key",
        )

    phone = normalize_phone(request.phone) or ""

    # Identify caller by phone
    identity = await auth_service.identify_by_phone(db, phone)

    if not identity or identity.get("role") != "master":
        return WhatsAppConsoleResponse(
            reply=console_service.ACCESS_DENIED,
        )

    # Create session service when Redis is available
    manager = get_redis_manager()
    if manager is None:
        return WhatsAppConsoleResponse(reply=CONSOLE_STATE_UNAVAILABLE_REPLY)

    session_service = WhatsAppSessionService(
        connection_manager=manager,
        ttl_seconds=settings.whatsapp_session_ttl_minutes * 60,
    )

    # Create tenant adapter for console service
    adapter = _TenantConsoleAdapter(tenant_service, db)

    try:
        reply = await console_service.process_message(
            phone=phone,
            message=request.message,
            is_master=True,
            session_service=session_service,
            tenant_service=adapter,
        )
    except Exception:
        # Both Redis stores are unavailable, connection/timeout errors,
        # or any other transient infrastructure failure.
        # Return relayable unavailable reply — never degrade to stateless
        # and never return HTTP 500 to n8n.
        return WhatsAppConsoleResponse(reply=CONSOLE_STATE_UNAVAILABLE_REPLY)

    return WhatsAppConsoleResponse(reply=reply)
