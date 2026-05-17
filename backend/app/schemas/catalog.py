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
