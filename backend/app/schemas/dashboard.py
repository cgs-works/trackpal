from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field
from uuid import UUID

from app.schemas.tenant_settings import CurrencyMeta


class ClientActiveSubscription(BaseModel):
    """Active subscription for a client's dashboard view."""

    id: UUID
    service_name: str
    service_icon: str | None = None
    plan_name: str
    plan_price: Decimal | None = None
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
    tenant_plan: str
    mailbox_status: str
    enabled_code_services: list[str] = Field(default_factory=list)
    access_control_count: int = 0
    active_clients: int | None = None
    catalog_services: int | None = None
    active_subscriptions: int | None = None
    subscriptions_expiring_soon: int | None = None


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
    currency: CurrencyMeta | None = None
