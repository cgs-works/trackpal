from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.tenant_service import TenantService

UNKNOWN_PHONE_REPLY = (
    "❌ No tienes acceso a la consola. "
    "El número de teléfono no está registrado en el sistema."
)

TENANT_CONSOLE_PLACEHOLDER = (
    "🤖 *TrackPal Consola de Administración*\n\n"
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
        profile = await self._service.get_tenant(self._db, UUID(tenant_id))
        if profile is None:
            return None
        return _TenantConsoleItem(profile)

    async def get_tenant_by_username(self, username: str) -> _TenantConsoleItem | None:
        from app.repositories import users_repository

        user = await users_repository.get_by_username(self._db, username)
        if user is None or user.role != "tenant":
            return None
        return await self.get_tenant(str(user.id))

    async def create_tenant(self, payload: dict) -> dict:
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
