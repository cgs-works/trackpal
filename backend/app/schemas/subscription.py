import uuid
from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel, ConfigDict, field_validator, model_validator


class SubscriptionCreate(BaseModel):
    model_config = ConfigDict()

    client_id: uuid.UUID
    service_id: uuid.UUID
    plan_id: uuid.UUID
    streaming_email: str
    streaming_password: Optional[str] = None
    profile_name: Optional[str] = None
    profile_pin: Optional[str] = None
    duration_type: str
    starts_at: datetime
    expires_at: Optional[datetime] = None

    @field_validator("duration_type")
    @classmethod
    def validate_duration_type(cls, v: str) -> str:
        valid_durations = {"1_month", "3_months", "6_months", "9_months", "1_year", "custom"}
        if v not in valid_durations:
            raise ValueError(f"duration_type must be one of {valid_durations}")
        return v

    @model_validator(mode="after")
    def validate_rules(self) -> "SubscriptionCreate":
        if self.profile_pin and not self.profile_name:
            raise ValueError("profile_pin requires profile_name")
        if self.duration_type == "custom" and not self.expires_at:
            raise ValueError("custom duration requires expires_at")
        return self


class SubscriptionUpdate(BaseModel):
    model_config = ConfigDict()

    client_id: Optional[uuid.UUID] = None
    service_id: Optional[uuid.UUID] = None
    plan_id: Optional[uuid.UUID] = None
    streaming_email: Optional[str] = None
    streaming_password: Optional[str] = None
    profile_name: Optional[str] = None
    profile_pin: Optional[str] = None
    duration_type: Optional[str] = None
    starts_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None

    @field_validator("duration_type")
    @classmethod
    def validate_duration_type(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        valid_durations = {"1_month", "3_months", "6_months", "9_months", "1_year", "custom"}
        if v not in valid_durations:
            raise ValueError(f"duration_type must be one of {valid_durations}")
        return v

    @model_validator(mode="after")
    def validate_rules(self) -> "SubscriptionUpdate":
        # Note: deeper validation with existing database state is done in the service layer
        if self.profile_pin and self.profile_name == "":
            raise ValueError("profile_pin requires profile_name")
        if self.duration_type == "custom" and not self.expires_at:
            raise ValueError("custom duration requires expires_at")
        return self


class SubscriptionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    client_id: uuid.UUID
    service_id: uuid.UUID
    plan_id: uuid.UUID
    streaming_email: str
    profile_name: Optional[str] = None
    duration_type: str
    starts_at: datetime
    expires_at: datetime
    cancelled_at: Optional[datetime] = None
    status: str
    created_at: datetime
    updated_at: datetime
    has_password: bool
    has_pin: bool

    @model_validator(mode="before")
    @classmethod
    def convert_from_orm(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            # It's an ORM object
            return {
                "id": data.id,
                "tenant_id": data.tenant_id,
                "client_id": data.client_id,
                "service_id": data.service_id,
                "plan_id": data.plan_id,
                "streaming_email": data.streaming_email,
                "profile_name": data.profile_name,
                "duration_type": data.duration_type,
                "starts_at": data.starts_at,
                "expires_at": data.expires_at,
                "cancelled_at": data.cancelled_at,
                "status": data.status,
                "created_at": data.created_at,
                "updated_at": data.updated_at,
                "has_password": bool(data.streaming_password_encrypted),
                "has_pin": bool(data.profile_pin_encrypted),
            }
        else:
            data["has_password"] = bool(data.get("streaming_password_encrypted") or data.get("has_password"))
            data["has_pin"] = bool(data.get("profile_pin_encrypted") or data.get("has_pin"))
            return data


class SubscriptionEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    subscription_id: uuid.UUID
    event_type: str
    notes: Optional[str] = None
    event_metadata: Optional[Any] = None
    created_at: datetime
    updated_at: datetime

    @model_validator(mode="before")
    @classmethod
    def convert_from_orm(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return {
                "id": data.id,
                "tenant_id": data.tenant_id,
                "subscription_id": data.subscription_id,
                "event_type": data.event_type,
                "notes": data.notes,
                "event_metadata": data.event_metadata,
                "created_at": data.created_at,
                "updated_at": data.updated_at,
            }
        return data


class SubscriptionReminderSettingsResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    timezone: str
    warning_days: list[int]
    reminder_time: str
    recipient_mode: str
    created_at: datetime
    updated_at: datetime


class SubscriptionReminderSettingsUpdate(BaseModel):
    model_config = ConfigDict()

    timezone: Optional[str] = None
    warning_days: Optional[list[int]] = None
    reminder_time: Optional[str] = None
    recipient_mode: Optional[str] = None

    @field_validator("reminder_time")
    @classmethod
    def validate_reminder_time(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        parts = v.split(":")
        if len(parts) != 2:
            raise ValueError("reminder_time must be in HH:MM format")
        try:
            h, m = int(parts[0]), int(parts[1])
            if not (0 <= h <= 23 and 0 <= m <= 59):
                raise ValueError()
        except ValueError:
            raise ValueError("reminder_time must be a valid time in HH:MM format")
        return v

    @field_validator("recipient_mode")
    @classmethod
    def validate_recipient_mode(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        valid_modes = {"tenant_only", "client_only", "tenant_client", "tenant_and_client"}
        if v not in valid_modes:
            raise ValueError(f"recipient_mode must be one of {valid_modes}")
        return v


class SubscriptionRevealResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    streaming_password: Optional[str] = None
    profile_pin: Optional[str] = None

