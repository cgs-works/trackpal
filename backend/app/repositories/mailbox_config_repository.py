"""Mailbox config repository — tenant_mailboxes CRUD."""

from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import TenantMailbox


async def get_by_tenant(db: AsyncSession, tenant_id: UUID) -> TenantMailbox | None:
    """Get mailbox config for a tenant (unique per tenant)."""
    result = await db.execute(
        select(TenantMailbox).where(TenantMailbox.tenant_id == tenant_id)
    )
    return result.scalar_one_or_none()


async def get_by_id(
    db: AsyncSession, mailbox_id: UUID, tenant_id: UUID | None = None
) -> TenantMailbox | None:
    """Get mailbox by id, optionally scoped to tenant."""
    stmt = select(TenantMailbox).where(TenantMailbox.id == mailbox_id)
    if tenant_id is not None:
        stmt = stmt.where(TenantMailbox.tenant_id == tenant_id)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def create(
    db: AsyncSession, tenant_id: UUID, mailbox: TenantMailbox
) -> TenantMailbox:
    """Create a new mailbox config for a tenant."""
    mailbox.tenant_id = tenant_id
    db.add(mailbox)
    await db.flush()
    return mailbox


async def update(
    db: AsyncSession, mailbox: TenantMailbox, **kwargs: Any
) -> TenantMailbox:
    """Update mailbox config fields in place."""
    for field, value in kwargs.items():
        setattr(mailbox, field, value)
    await db.flush()
    return mailbox


async def update_status(
    db: AsyncSession, mailbox: TenantMailbox, status: str, error: str | None = None
) -> TenantMailbox:
    """Update mailbox status and optional error message."""
    mailbox.status = status
    if error is not None:
        mailbox.last_connection_error = error
    await db.flush()
    return mailbox


async def update_connection_test(
    db: AsyncSession, mailbox: TenantMailbox, success: bool, error: str | None = None
) -> TenantMailbox:
    """Record connection test result."""
    from datetime import datetime, timezone

    mailbox.last_connection_test_at = datetime.now(timezone.utc)
    if success:
        mailbox.last_connection_error = None
    elif error is not None:
        mailbox.last_connection_error = error
    await db.flush()
    return mailbox


async def delete(db: AsyncSession, mailbox: TenantMailbox) -> None:
    """Delete a mailbox config."""
    await db.delete(mailbox)
    await db.flush()


async def count_by_status(db: AsyncSession, status: str) -> int:
    """Count mailboxes with a given status."""
    result = await db.execute(
        select(func.count())
        .select_from(TenantMailbox)
        .where(TenantMailbox.status == status)
    )
    return int(result.scalar_one())


__all__ = [
    "get_by_tenant",
    "get_by_id",
    "create",
    "update",
    "update_status",
    "update_connection_test",
    "delete",
    "count_by_status",
]
