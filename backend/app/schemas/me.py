from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, field_validator

from app.core import VALID_LOCALES
from app.core.input_validation import (
    validate_email,
    validate_full_name,
    validate_phone,
    validate_password_policy,
)


class ProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    role: str
    username: str
    name: str | None = None
    full_name: str | None = None
    local_username: str | None = None
    tenant_id: UUID | None = None
    tenant_name: str | None = None
    client_prefix: str | None = None
    locale: str | None = None
    email: str | None = None
    phone: str | None = None
    is_active: bool | None = None
    created_at: datetime
    updated_at: datetime


class ProfileUpdate(BaseModel):
    model_config = ConfigDict()

    full_name: str | None = None
    email: str | None = None
    phone: str | None = None
    name: str | None = None
    locale: str | None = None

    @field_validator("full_name")
    @classmethod
    def validate_full_name_field(cls, v: str | None) -> str | None:
        if v is None:
            return None
        return validate_full_name(v)

    @field_validator("locale")
    @classmethod
    def validate_locale_field(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v = v.strip().lower()
        if v not in VALID_LOCALES:
            raise ValueError(f"Locale must be one of: {', '.join(VALID_LOCALES)}")
        return v

    @field_validator("name")
    @classmethod
    def validate_name_field(cls, v: str | None) -> str | None:
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


class PasswordChange(BaseModel):
    old_password: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def validate_new_password_field(cls, v: str) -> str:
        return validate_password_policy(v)
