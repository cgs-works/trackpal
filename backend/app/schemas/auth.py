from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.core.tenant_plan import TenantPlan
from app.models import DemoTenantStatus


class LoginRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    username: str
    password: str


class UserInfo(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    role: str
    username: str


class TokenResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserInfo
    active_tenant_id: UUID | None = None
    tenant_plan: TenantPlan | None = None
    is_demo: bool = False
    demo_status: DemoTenantStatus | None = None
    demo_activated_at: datetime | None = None
    demo_expires_at: datetime | None = None
    demo_credentials_version: int | None = None
    server_time: datetime


class DemoHeartbeatResponse(BaseModel):
    is_demo: bool
    tenant_plan: TenantPlan | None = None
    demo_status: DemoTenantStatus | None = None
    demo_activated_at: datetime | None = None
    demo_expires_at: datetime | None = None
    demo_credentials_version: int | None = None
    server_time: datetime


class RefreshRequest(BaseModel):
    refresh_token: str
    active_tenant_id: UUID | None = None


class SwitchTenantRequest(BaseModel):
    tenant_id: UUID | None = None


class IdentifyResponse(BaseModel):
    user_id: UUID
    role: str
    username: str
