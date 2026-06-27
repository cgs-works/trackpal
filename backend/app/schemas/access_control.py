from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, field_validator

from app.core.input_validation import validate_phone


class AccessControlBlockCreate(BaseModel):
    phone: str

    @field_validator("phone")
    @classmethod
    def validate_phone_field(cls, value: str) -> str:
        normalized = validate_phone(value)
        if normalized is None:
            raise ValueError("Phone is required")
        return normalized


class AccessControlBlockResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    phone: str | None
    whatsapp_lid: str | None
    created_at: datetime
    updated_at: datetime
