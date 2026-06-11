"""Subscription creation/update/mutation schemas."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from app.services.subscription_service.timezone_catalog import validate_timezone


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
        valid_durations = {
            "1_month",
            "3_months",
            "6_months",
            "9_months",
            "1_year",
            "custom",
        }
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
        valid_durations = {
            "1_month",
            "3_months",
            "6_months",
            "9_months",
            "1_year",
            "custom",
        }
        if v not in valid_durations:
            raise ValueError(f"duration_type must be one of {valid_durations}")
        return v

    @model_validator(mode="after")
    def validate_rules(self) -> "SubscriptionUpdate":
        if self.profile_pin and self.profile_name == "":
            raise ValueError("profile_pin requires profile_name")
        if self.duration_type == "custom" and not self.expires_at:
            raise ValueError("custom duration requires expires_at")
        return self


class SubscriptionReminderSettingsUpdate(BaseModel):
    model_config = ConfigDict()

    timezone: Optional[str] = None
    warning_days: Optional[list[int]] = None
    reminder_time: Optional[str] = None
    recipient_mode: Optional[str] = None
    reminders_enabled: Optional[bool] = None
    custom_message_tenant: Optional[str] = None
    custom_message_client: Optional[str] = None

    @field_validator("timezone")
    @classmethod
    def validate_timezone_field(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        if not validate_timezone(v):
            raise ValueError(f"'{v}' is not a valid IANA timezone identifier")
        return v

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
        valid_modes = {
            "tenant_only",
            "client_only",
            "tenant_client",
            "tenant_and_client",
            "both",
        }
        if v not in valid_modes:
            raise ValueError(f"recipient_mode must be one of {valid_modes}")
        return v


class MarkFailedRequest(BaseModel):
    reason: Optional[str] = None
