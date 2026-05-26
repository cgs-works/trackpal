from datetime import datetime

from pydantic import BaseModel, Field
from uuid import UUID


class ClientActiveSubscription(BaseModel):
    """Active subscription for a client's dashboard view."""

    id: UUID
    service_name: str
    plan_name: str
    status: str
    starts_at: datetime
    expires_at: datetime


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
    phone: str | None
    tenant_id: UUID
    tenant_name: str
    client_prefix: str
    is_active: bool
    subscriptions: list[ClientActiveSubscription] = Field(default_factory=list)
