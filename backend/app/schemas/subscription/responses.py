"""Subscription response/read schemas."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, model_validator


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
    reminders_enabled: bool
    created_at: datetime
    updated_at: datetime


class SubscriptionRevealResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    streaming_password: Optional[str] = None
    profile_pin: Optional[str] = None


class ReminderPayload(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    subscription_id: uuid.UUID
    tenant_id: uuid.UUID
    recipient_type: str
    recipient_phone: str
    message: str
    evolution_instance_name: Optional[str] = None
    days_before_expiry: int


class ReminderPendingResponse(BaseModel):
    items: list[ReminderPayload]
    next_cursor: Optional[str] = None


class ReminderLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    subscription_id: uuid.UUID
    recipient_type: str
    recipient_phone: Optional[str] = None
    days_before_expiry: int
    sent_for_date: date
    status: str
    attempt_count: int
    last_error: Optional[str] = None
    sent_at: Optional[datetime] = None
