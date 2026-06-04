from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ServiceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)


class ServiceUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)


class ServiceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    tenant_id: UUID
    name: str
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
