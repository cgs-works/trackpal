"""Blocked Client repository — blocked_clients table queries."""

from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.blocked_client import BlockedClient


def _identity_clause(phone: str | None, whatsapp_lid: str | None):
    if phone and whatsapp_lid:
        return or_(
            BlockedClient.phone == phone, BlockedClient.whatsapp_lid == whatsapp_lid
        )
    if phone:
        return BlockedClient.phone == phone
    if whatsapp_lid:
        return BlockedClient.whatsapp_lid == whatsapp_lid
    return None


async def create(
    db: AsyncSession,
    tenant_id: UUID,
    *,
    phone: str | None = None,
    whatsapp_lid: str | None = None,
) -> BlockedClient:
    """Create a block for a tenant-scoped identity.

    At least one of *phone* or *whatsapp_lid* must be provided.
    """
    if not phone and not whatsapp_lid:
        raise ValueError(
            "At least one identity field (phone or whatsapp_lid) is required"
        )

    block = BlockedClient(
        tenant_id=tenant_id,
        phone=phone,
        whatsapp_lid=whatsapp_lid,
    )
    db.add(block)
    await db.flush()
    return block


async def list_active(db: AsyncSession, tenant_id: UUID) -> list[BlockedClient]:
    """List all existing blocks for a tenant, newest first."""
    result = await db.execute(
        select(BlockedClient)
        .where(BlockedClient.tenant_id == tenant_id)
        .order_by(BlockedClient.created_at.desc())
    )
    return list(result.scalars().all())


async def find_active(
    db: AsyncSession,
    tenant_id: UUID,
    *,
    phone: str | None = None,
    whatsapp_lid: str | None = None,
) -> BlockedClient | None:
    """Find a block by phone or LID within a tenant."""
    identity_clause = _identity_clause(phone, whatsapp_lid)
    if identity_clause is None:
        return None
    result = await db.execute(
        select(BlockedClient).where(
            BlockedClient.tenant_id == tenant_id, identity_clause
        )
    )
    return result.scalar_one_or_none()


async def unblock(
    db: AsyncSession,
    tenant_id: UUID,
    block_id: UUID,
) -> BlockedClient | None:
    """Delete a specific block. Returns the deleted row or None."""
    result = await db.execute(
        select(BlockedClient).where(
            BlockedClient.id == block_id,
            BlockedClient.tenant_id == tenant_id,
        )
    )
    block = result.scalar_one_or_none()
    if block is not None:
        await db.delete(block)
        await db.flush()
    return block


async def clear_identity(
    db: AsyncSession,
    tenant_id: UUID,
    *,
    phone: str | None = None,
    whatsapp_lid: str | None = None,
) -> int:
    """Delete all blocks for an identity when a Client is created.

    Returns the number of blocks deleted.
    """
    identity_clause = _identity_clause(phone, whatsapp_lid)
    if identity_clause is None:
        return 0
    result = await db.execute(
        select(BlockedClient).where(
            BlockedClient.tenant_id == tenant_id, identity_clause
        )
    )
    blocks = list(result.scalars().all())
    for block in blocks:
        await db.delete(block)
    await db.flush()
    return len(blocks)


__all__ = [
    "create",
    "list_active",
    "find_active",
    "unblock",
    "clear_identity",
]
