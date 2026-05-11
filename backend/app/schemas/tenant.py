from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, field_validator


class TenantCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    full_name: str
    email: str | None = None
    phone: str | None = None
    username: str
    password: str | None = None
    evolution_instance_name: str | None = None

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str | None) -> str | None:
        if v is not None and len(v) < 6:
            raise ValueError("Password must be at least 6 characters")
        return v


class TenantUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    full_name: str | None = None
    email: str | None = None
    phone: str | None = None
    evolution_instance_name: str | None = None


class TenantResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    full_name: str
    email: str | None
    phone: str | None
    evolution_instance_name: str | None
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
