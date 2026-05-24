"""Reminder log status updates and stubs."""

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import restore_rls_context
from app.models.subscription import SubscriptionReminderLog


async def mark_reminder_sent(
    db: AsyncSession, log_id: uuid.UUID
) -> dict[str, Any] | None:
    res = await db.execute(
        select(SubscriptionReminderLog).where(SubscriptionReminderLog.id == log_id)
    )
    log = res.scalar_one_or_none()
    if not log:
        return None

    now = datetime.now(timezone.utc)
    log.status = "sent"
    log.sent_at = now
    log.last_error = None
    await db.commit()
    await restore_rls_context(db)

    return {
        "id": str(log.id),
        "status": log.status,
        "sent_at": log.sent_at.isoformat() if log.sent_at else None,
    }


async def mark_reminder_failed(
    db: AsyncSession, log_id: uuid.UUID, reason: str | None = None
) -> dict[str, Any] | None:
    res = await db.execute(
        select(SubscriptionReminderLog).where(SubscriptionReminderLog.id == log_id)
    )
    log = res.scalar_one_or_none()
    if not log:
        return None

    log.attempt_count = (log.attempt_count or 0) + 1
    log.last_error = reason or "Unknown error"

    if log.attempt_count >= 3:
        log.status = "failed"

    await db.commit()
    await restore_rls_context(db)

    return {
        "id": str(log.id),
        "status": log.status,
        "attempt_count": log.attempt_count,
        "last_error": log.last_error,
    }


async def run_reminders_stub() -> list[dict[str, Any]]:
    """Placeholder for reminders in the job endpoint.

    Actual reminders are generated via ``generate_reminder_payloads``.
    """
    return []
