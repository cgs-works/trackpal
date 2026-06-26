from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.input_validation import (
    validate_client_prefix,
    validate_email,
    validate_full_name,
    validate_phone,
    validate_username,
)
from app.core.tenant_plan import TenantPlan, normalize_tenant_plan


class TenantCreate(BaseModel):
    model_config = ConfigDict()

    full_name: str
    email: str | None = None
    phone: str | None = None
    username: str
    password: str | None = None
    evolution_instance_name: str = Field(min_length=1)
    client_prefix: str | None = None
    plan: TenantPlan

    @field_validator("plan")
    @classmethod
    def validate_plan_field(cls, v: str) -> TenantPlan:
        return normalize_tenant_plan(v)

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str | None) -> str | None:
        if v is not None and len(v) < 6:
            raise ValueError("Password must be at least 6 characters")
        return v

    @field_validator("username")
    @classmethod
    def validate_username_field(cls, v: str) -> str:
        return validate_username(v)

    @field_validator("full_name")
    @classmethod
    def validate_full_name_field(cls, v: str) -> str:
        return validate_full_name(v)

    @field_validator("email")
    @classmethod
    def validate_email_field(cls, v: str | None) -> str | None:
        return validate_email(v)

    @field_validator("phone")
    @classmethod
    def validate_phone_field(cls, v: str | None) -> str | None:
        return validate_phone(v)

    @field_validator("client_prefix")
    @classmethod
    def validate_client_prefix_field(cls, v: str | None) -> str | None:
        if v is None:
            return None
        return validate_client_prefix(v)


class TenantUpdate(BaseModel):
    model_config = ConfigDict()

    full_name: str | None = None
    email: str | None = None
    phone: str | None = None
    evolution_instance_name: str | None = None
    client_prefix: str | None = None
    plan: TenantPlan | None = None

    @field_validator("plan")
    @classmethod
    def validate_plan_field(cls, v: str | None) -> TenantPlan | None:
        if v is None:
            return None
        return normalize_tenant_plan(v)

    @field_validator("full_name")
    @classmethod
    def validate_full_name_field(cls, v: str | None) -> str | None:
        if v is None:
            return None
        return validate_full_name(v)

    @field_validator("email")
    @classmethod
    def validate_email_field(cls, v: str | None) -> str | None:
        return validate_email(v)

    @field_validator("phone")
    @classmethod
    def validate_phone_field(cls, v: str | None) -> str | None:
        return validate_phone(v)

    @field_validator("client_prefix")
    @classmethod
    def validate_client_prefix_field(cls, v: str | None) -> str | None:
        if v is None:
            return None
        return validate_client_prefix(v)


class TenantResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    full_name: str
    client_prefix: str
    email: str | None
    phone: str | None
    evolution_instance_name: str | None
    plan: TenantPlan
    is_active: bool
    username: str
    created_at: datetime


class TenantMeta(BaseModel):
    total: int
    active: int
    inactive: int


class TenantListResponse(BaseModel):
    data: list[TenantResponse]
    meta: TenantMeta
