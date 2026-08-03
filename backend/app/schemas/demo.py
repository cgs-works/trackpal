from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core import VALID_LOCALES
from app.core.input_validation import validate_full_name
from app.core.tenant_plan import TenantPlan, normalize_tenant_plan
from app.models import DemoTenantStatus


class DemoTenantCreate(BaseModel):
    """Master input for creating a Demo Tenant identity."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=200)
    plan: TenantPlan
    locale: str = "en"

    @field_validator("locale")
    @classmethod
    def validate_locale(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in VALID_LOCALES:
            raise ValueError(f"Locale must be one of: {', '.join(VALID_LOCALES)}")
        return normalized

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        return validate_full_name(value)

    @field_validator("plan")
    @classmethod
    def validate_plan(cls, value: str) -> TenantPlan:
        return normalize_tenant_plan(value)


class DemoTenantResponse(BaseModel):
    """Lifecycle-only Demo Tenant representation for Master management."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    plan: TenantPlan
    locale: str
    status: DemoTenantStatus
    username: str
    created_at: datetime
    demo_activated_at: datetime | None
    demo_expires_at: datetime | None
    server_time: datetime
    remaining_seconds: int | None


class DemoTenantCredentialsResponse(DemoTenantResponse):
    """One-time credential response for creation or replacement."""

    plain_password: str
