from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, field_validator

from app.core.input_validation import (
    validate_client_local_username,
    validate_full_name,
    validate_phone,
    validate_password_policy,
)


class ClientCreate(BaseModel):
    model_config = ConfigDict()

    full_name: str
    local_username: str
    phone: str | None = None
    password: str

    @field_validator("full_name")
    @classmethod
    def validate_full_name_field(cls, v: str) -> str:
        return validate_full_name(v)

    @field_validator("local_username")
    @classmethod
    def validate_local_username_field(cls, v: str) -> str:
        return validate_client_local_username(v)

    @field_validator("phone")
    @classmethod
    def validate_phone_field(cls, v: str | None) -> str | None:
        return validate_phone(v)

    @field_validator("password")
    @classmethod
    def validate_password_field(cls, v: str) -> str:
        return validate_password_policy(v)


class ClientUpdate(BaseModel):
    model_config = ConfigDict()

    full_name: str | None = None
    local_username: str | None = None
    phone: str | None = None

    @field_validator("full_name")
    @classmethod
    def validate_full_name_field(cls, v: str | None) -> str | None:
        if v is None:
            return None
        return validate_full_name(v)

    @field_validator("local_username")
    @classmethod
    def validate_local_username_field(cls, v: str | None) -> str | None:
        if v is None:
            return None
        return validate_client_local_username(v)

    @field_validator("phone")
    @classmethod
    def validate_phone_field(cls, v: str | None) -> str | None:
        return validate_phone(v)


class ClientResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    owner_user_id: UUID
    full_name: str
    username: str
    phone: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime

