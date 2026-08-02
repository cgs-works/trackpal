"""Safe Master-facing schemas for the lookup executor registry."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class LookupExecutorCreateRequest(BaseModel):
    """Create an executor draft and its protocol credentials."""

    name: str = Field(min_length=1, max_length=255)
    provider_label: str = Field(min_length=1, max_length=50)
    base_url: str = Field(default="", max_length=500)
    transport_mode: str = Field(default="https", max_length=30)
    max_concurrency: int = Field(default=1, ge=1)
    hosting_account_email: str | None = Field(default=None, max_length=255)
    hosting_account_password: str | None = Field(default=None, max_length=500)
    dashboard_url: str | None = Field(default=None, max_length=500)


class LookupExecutorUpdateRequest(BaseModel):
    """Update non-secret executor configuration."""

    name: str | None = Field(default=None, min_length=1, max_length=255)
    provider_label: str | None = Field(default=None, min_length=1, max_length=50)
    base_url: str | None = Field(default=None, max_length=500)
    transport_mode: str | None = Field(default=None, max_length=30)
    max_concurrency: int | None = Field(default=None, ge=1)
    hosting_account_email: str | None = Field(default=None, max_length=255)
    hosting_account_password: str | None = Field(default=None, max_length=500)
    dashboard_url: str | None = Field(default=None, max_length=500)


class LookupExecutorResponse(BaseModel):
    """Executor detail that deliberately omits all encrypted credential values."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    provider_label: str
    base_url: str
    transport_mode: str
    lifecycle_status: str
    health_status: str
    requires_reverification: bool
    max_concurrency: int
    secret_version: int
    pending_secret_version: int | None = None
    has_hosting_password: bool = False
    last_health_check_at: datetime | None = None
    last_success_at: datetime | None = None
    last_error_safe: str | None = None
    active_jobs: int = 0
    created_at: datetime
    updated_at: datetime

    @model_validator(mode="before")
    @classmethod
    def hide_encrypted_values(cls, data: Any) -> Any:
        """Convert ORM objects while exposing only credential presence."""
        if not isinstance(data, dict):
            return {
                field: getattr(data, field)
                for field in (
                    "id",
                    "name",
                    "provider_label",
                    "base_url",
                    "transport_mode",
                    "lifecycle_status",
                    "health_status",
                    "requires_reverification",
                    "max_concurrency",
                    "secret_version",
                    "pending_secret_version",
                    "last_health_check_at",
                    "last_success_at",
                    "last_error_safe",
                    "created_at",
                    "updated_at",
                )
            } | {
                "has_hosting_password": bool(
                    getattr(data, "hosting_account_password_encrypted", None)
                ),
                "active_jobs": int(getattr(data, "active_jobs", 0)),
            }
        values = dict(data)
        values["has_hosting_password"] = bool(
            values.get("hosting_account_password_encrypted")
            or values.get("has_hosting_password")
        )
        values.pop("secret_encrypted", None)
        values.pop("pending_secret_encrypted", None)
        values.pop("hosting_account_password_encrypted", None)
        return values


class LookupExecutorCreateResponse(BaseModel):
    """One-time enrollment response containing the generated plain secret."""

    executor: LookupExecutorResponse
    plain_secret: str
