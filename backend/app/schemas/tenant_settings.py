from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, field_validator

from app.core import VALID_LOCALES
from app.services.subscription_service.timezone_catalog import validate_timezone


class TenantSettingsResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    tenant_id: UUID
    locale: str
    timezone: str | None
    created_at: datetime
    updated_at: datetime


class TenantSettingsUpdate(BaseModel):
    model_config = ConfigDict()

    locale: str | None = None
    timezone: str | None = None

    @field_validator("locale")
    @classmethod
    def validate_locale_field(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip().lower()
        if normalized not in VALID_LOCALES:
            raise ValueError(f"Locale must be one of: {', '.join(VALID_LOCALES)}")
        return normalized

    @field_validator("timezone")
    @classmethod
    def validate_timezone_field(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if not validate_timezone(value):
            raise ValueError(f"'{value}' is not a valid IANA timezone identifier")
        return value
