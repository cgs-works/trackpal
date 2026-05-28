"""Dedupe delivery log repository — mail_code_delivery_log insert/check."""

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import MailCodeDeliveryLog

RETENTION_DAYS = 90


async def is_duplicate(
    db: AsyncSession,
    tenant_id: UUID,
    mailbox_id: UUID,
    service_key: str,
    message_id: str | None,
    fingerprint: str,
) -> bool:
    """Check if a code has already been delivered via Message-ID + fingerprint.

    Primary match: (tenant_id, mailbox_id, service_key, message_id, fingerprint).
    Fallback (null Message-ID): (tenant_id, mailbox_id, service_key, fingerprint).
    """
    stmt = select(MailCodeDeliveryLog.id).where(
        MailCodeDeliveryLog.tenant_id == tenant_id,
        MailCodeDeliveryLog.mailbox_id == mailbox_id,
        MailCodeDeliveryLog.service_key == service_key,
        MailCodeDeliveryLog.fingerprint == fingerprint,
    )

    if message_id:
        stmt = stmt.where(MailCodeDeliveryLog.message_id == message_id)
    else:
        stmt = stmt.where(MailCodeDeliveryLog.message_id.is_(None))

    result = await db.execute(stmt)
    return result.first() is not None


async def record_delivery(
    db: AsyncSession,
    tenant_id: UUID,
    mailbox_id: UUID,
    service_key: str,
    message_id: str | None,
    fingerprint: str,
) -> MailCodeDeliveryLog:
    """Record a code delivery for dedupe tracking."""
    entry = MailCodeDeliveryLog(
        tenant_id=tenant_id,
        mailbox_id=mailbox_id,
        service_key=service_key,
        message_id=message_id,
        fingerprint=fingerprint,
        delivered_at=datetime.now(timezone.utc),
    )
    db.add(entry)
    await db.flush()
    return entry


async def delete_older_than(db: AsyncSession, before: datetime | None = None) -> int:
    """Delete delivery log entries older than cutoff.

    Default: RETENTION_DAYS days ago. Returns count deleted.
    """
    cutoff = before or (datetime.now(timezone.utc))
    from datetime import timedelta

    cutoff = datetime.now(timezone.utc) - timedelta(days=RETENTION_DAYS)

    result = await db.execute(
        select(MailCodeDeliveryLog).where(MailCodeDeliveryLog.delivered_at < cutoff)
    )
    entries = list(result.scalars().all())
    for entry in entries:
        await db.delete(entry)
    await db.flush()
    return len(entries)


__all__ = [
    "is_duplicate",
    "record_delivery",
    "delete_older_than",
]
