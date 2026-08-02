"""Dedupe delivery log repository — mail_code_delivery_log insert/check."""

from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert as postgres_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
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
    cutoff = before or (datetime.now(timezone.utc) - timedelta(days=RETENTION_DAYS))

    result = await db.execute(
        select(MailCodeDeliveryLog).where(MailCodeDeliveryLog.delivered_at < cutoff)
    )
    entries = list(result.scalars().all())
    for entry in entries:
        await db.delete(entry)
    await db.flush()
    return len(entries)


async def record_delivery_atomic(
    db: AsyncSession,
    tenant_id: UUID,
    mailbox_id: UUID,
    service_key: str,
    message_id: str | None,
    fingerprint: str,
) -> bool:
    """Insert a dedupe row with one database-level conflict decision.

    PostgreSQL and SQLite both use partial unique indexes so the fallback key
    without a message ID is unique as well.  ``ON CONFLICT DO NOTHING`` makes
    the insert safe when concurrent transactions race before either can see
    the other's row.
    """
    values = {
        "tenant_id": tenant_id,
        "mailbox_id": mailbox_id,
        "service_key": service_key,
        "message_id": message_id,
        "fingerprint": fingerprint,
        "delivered_at": datetime.now(timezone.utc),
    }
    if message_id is None:
        index_elements = [
            MailCodeDeliveryLog.tenant_id,
            MailCodeDeliveryLog.mailbox_id,
            MailCodeDeliveryLog.service_key,
            MailCodeDeliveryLog.fingerprint,
        ]
        index_where = text("message_id IS NULL")
    else:
        index_elements = [
            MailCodeDeliveryLog.tenant_id,
            MailCodeDeliveryLog.mailbox_id,
            MailCodeDeliveryLog.service_key,
            MailCodeDeliveryLog.message_id,
            MailCodeDeliveryLog.fingerprint,
        ]
        index_where = text("message_id IS NOT NULL")

    dialect_name = db.get_bind().dialect.name
    if dialect_name == "postgresql":
        statement = postgres_insert(MailCodeDeliveryLog)
    elif dialect_name == "sqlite":
        statement = sqlite_insert(MailCodeDeliveryLog)
    else:
        raise RuntimeError(
            f"Atomic delivery deduplication is unsupported for {dialect_name}"
        )
    statement = statement.values(**values).on_conflict_do_nothing(
        index_elements=index_elements,
        index_where=index_where,
    )
    result = await db.execute(statement)
    return result.rowcount == 1


__all__ = [
    "is_duplicate",
    "record_delivery",
    "record_delivery_atomic",
    "delete_older_than",
]
