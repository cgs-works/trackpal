import re
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

ICON_REFERENCE_MAX_LENGTH = 255
ICON_REFERENCE_PATTERN = re.compile(
    r"^[a-z0-9]+(?:-[a-z0-9]+)*:[a-z0-9]+(?:-[a-z0-9]+)*$"
)


def normalize_icon_reference(value: str | None) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("invalid_icon_reference")
    cleaned = value.strip()
    if not cleaned:
        return None
    if (
        len(cleaned) > ICON_REFERENCE_MAX_LENGTH
        or ICON_REFERENCE_PATTERN.fullmatch(cleaned) is None
    ):
        raise ValueError("invalid_icon_reference")
    return cleaned


class ServiceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    icon: str | None = None

    @field_validator("icon", mode="before")
    @classmethod
    def clean_icon(cls, value: str | None) -> str | None:
        return normalize_icon_reference(value)


class ServiceUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    icon: str | None = None

    @field_validator("icon", mode="before")
    @classmethod
    def clean_icon(cls, value: str | None) -> str | None:
        return normalize_icon_reference(value)


class ServiceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    tenant_id: UUID
    name: str
    icon: str | None = None
    created_at: datetime
    updated_at: datetime


class PlanCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)


class PlanUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)


class PlanResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    tenant_id: UUID
    service_id: UUID
    name: str
    created_at: datetime
    updated_at: datetime


class CatalogDeleteSubscriptionRow(BaseModel):
    id: UUID
    streaming_email: str
    client_name: str | None = None
    client_phone: str | None = None
    service_name: str
    plan_name: str
    expires_at: datetime | None = None


class CatalogDeletePagination(BaseModel):
    page: int
    page_size: int
    total_items: int
    total_pages: int
    has_next: bool


class CatalogDeletePreview(BaseModel):
    target_type: str
    target_id: UUID
    target_name: str
    affected_plan_count: int = 0
    active_subscription_count: int
    historical_subscription_count: int
    total_subscription_count: int
    active_subscriptions: list[CatalogDeleteSubscriptionRow]
    pagination: CatalogDeletePagination
    note: str
