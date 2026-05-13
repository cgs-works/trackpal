from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.input_validation import (
    validate_email,
    validate_full_name,
    validate_phone,
    validate_username,
)


class TenantCreate(BaseModel):
    model_config = ConfigDict()

    full_name: str
    email: str | None = None
    phone: str | None = None
    username: str
    password: str | None = None
    evolution_instance_name: str = Field(min_length=1)

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str | None) -> str | None:
        if v is not None:
            v = v.strip()
            if v == "" or len(v) < 6:
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


class TenantUpdate(BaseModel):
    model_config = ConfigDict()

    full_name: str | None = None
    email: str | None = None
    phone: str | None = None
    evolution_instance_name: str | None = None

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
