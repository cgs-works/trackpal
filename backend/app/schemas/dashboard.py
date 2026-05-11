from pydantic import BaseModel


class MasterDashboardResponse(BaseModel):
    total_tenants: int
    active_tenants: int
    inactive_tenants: int


class TenantDashboardResponse(BaseModel):
    message: str = "Dashboard en construccion"
    full_name: str
    email: str | None
