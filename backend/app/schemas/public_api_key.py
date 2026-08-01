from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class PublicApiKeyUpdate(BaseModel):
    allowed_origins: list[str] = Field(default_factory=list, max_length=20)

    @field_validator("allowed_origins")
    @classmethod
    def clean_allowed_origins(cls, value: list[str]) -> list[str]:
        return list(dict.fromkeys(origin.strip() for origin in value))


class PublicApiKeyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    tenant_id: UUID
    api_key: str
    allowed_origins: list[str]
    created_at: datetime
    updated_at: datetime


class PublicCatalogPlan(BaseModel):
    id: UUID
    name: str


class PublicCatalogService(BaseModel):
    id: UUID
    name: str
    icon: str | None = None
    plans: list[PublicCatalogPlan]


class PublicCatalogResponse(BaseModel):
    services: list[PublicCatalogService]
