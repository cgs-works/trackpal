"""Shared helpers: expiration, commit, event creation."""

import uuid
from datetime import datetime, timedelta
from typing import Any, Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import UserFacingError
from app.models.subscription import SubscriptionEvent
from .constants import DURATION_MAP


def calculate_expiration(
    starts_at: datetime,
    duration_type: str,
    expires_at: Optional[datetime] = None,
) -> datetime:
    if duration_type == "custom":
        if not expires_at:
            raise ValueError("custom duration requires expires_at")
        return expires_at
    days = DURATION_MAP.get(duration_type)
    if not days:
        raise ValueError(f"Invalid duration_type: {duration_type}")
    return starts_at + timedelta(days=days)


async def commit_change(db: AsyncSession, err_code: str) -> None:
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise UserFacingError(err_code) from exc


async def create_event(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    subscription_id: uuid.UUID,
    event_type: str,
    notes: Optional[str] = None,
    metadata: Optional[Any] = None,
) -> SubscriptionEvent:
    event = SubscriptionEvent(
        tenant_id=tenant_id,
        subscription_id=subscription_id,
        event_type=event_type,
        notes=notes,
        event_metadata=metadata,
    )
    db.add(event)
    await db.flush()
    return event
