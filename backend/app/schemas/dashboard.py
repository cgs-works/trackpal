from pydantic import BaseModel
from uuid import UUID


class MasterDashboardResponse(BaseModel):
    total_tenants: int
    active_tenants: int
    inactive_tenants: int


class TenantDashboardResponse(BaseModel):
    message: str = "Dashboard en construccion"
    full_name: str
    email: str | None


class ClientDashboardResponse(BaseModel):
    message: str = "Dashboard de cliente"
    id: UUID
    full_name: str
    username: str
    local_username: str
    phone: str | None
    tenant_id: UUID
    tenant_name: str
    client_prefix: str
    is_active: bool
