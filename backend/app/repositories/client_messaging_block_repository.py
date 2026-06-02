"""Client Messaging Block repository — client_messaging_blocks table queries."""

from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.client_messaging_block import ClientMessagingBlock


async def create(
    db: AsyncSession,
    tenant_id: UUID,
    *,
    phone: str | None = None,
    whatsapp_lid: str | None = None,
) -> ClientMessagingBlock:
    """Create an active block for a tenant-scoped identity.

    At least one of *phone* or *whatsapp_lid* must be provided.
    """
    if not phone and not whatsapp_lid:
        raise ValueError(
            "At least one identity field (phone or whatsapp_lid) is required"
        )

    block = ClientMessagingBlock(
        tenant_id=tenant_id,
        phone=phone,
        whatsapp_lid=whatsapp_lid,
        is_active=True,
    )
    db.add(block)
    await db.flush()
    return block


async def list_active(db: AsyncSession, tenant_id: UUID) -> list[ClientMessagingBlock]:
    """List all active blocks for a tenant, newest first."""
    result = await db.execute(
        select(ClientMessagingBlock)
        .where(
            ClientMessagingBlock.tenant_id == tenant_id,
            ClientMessagingBlock.is_active,
        )
        .order_by(ClientMessagingBlock.created_at.desc())
    )
    return list(result.scalars().all())


async def find_active(
    db: AsyncSession,
    tenant_id: UUID,
    *,
    phone: str | None = None,
    whatsapp_lid: str | None = None,
) -> ClientMessagingBlock | None:
    """Find an active block by phone or LID within a tenant."""
    if not phone and not whatsapp_lid:
        return None
    stmt = select(ClientMessagingBlock).where(
        ClientMessagingBlock.tenant_id == tenant_id,
        ClientMessagingBlock.is_active,
    )
    if phone and whatsapp_lid:
        stmt = stmt.where(
            or_(
                ClientMessagingBlock.phone == phone,
                ClientMessagingBlock.whatsapp_lid == whatsapp_lid,
            )
        )
    elif phone:
        stmt = stmt.where(ClientMessagingBlock.phone == phone)
    else:
        stmt = stmt.where(ClientMessagingBlock.whatsapp_lid == whatsapp_lid)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def unblock(
    db: AsyncSession,
    tenant_id: UUID,
    block_id: UUID,
) -> ClientMessagingBlock | None:
    """Deactivate (soft-delete) a specific block. Returns the updated row or None."""
    result = await db.execute(
        select(ClientMessagingBlock).where(
            ClientMessagingBlock.id == block_id,
            ClientMessagingBlock.tenant_id == tenant_id,
            ClientMessagingBlock.is_active,
        )
    )
    block = result.scalar_one_or_none()
    if block is not None:
        block.is_active = False
        await db.flush()
    return block


async def clear_identity(
    db: AsyncSession,
    tenant_id: UUID,
    *,
    phone: str | None = None,
    whatsapp_lid: str | None = None,
) -> int:
    """Deactivate all active blocks for an identity (used when a Client is created).

    Returns the number of blocks deactivated.
    """
    if not phone and not whatsapp_lid:
        return 0
    stmt = select(ClientMessagingBlock).where(
        ClientMessagingBlock.tenant_id == tenant_id,
        ClientMessagingBlock.is_active,
    )
    if phone and whatsapp_lid:
        stmt = stmt.where(
            or_(
                ClientMessagingBlock.phone == phone,
                ClientMessagingBlock.whatsapp_lid == whatsapp_lid,
            )
        )
    elif phone:
        stmt = stmt.where(ClientMessagingBlock.phone == phone)
    else:
        stmt = stmt.where(ClientMessagingBlock.whatsapp_lid == whatsapp_lid)
    result = await db.execute(stmt)
    blocks = list(result.scalars().all())
    for block in blocks:
        block.is_active = False
    await db.flush()
    return len(blocks)


__all__ = [
    "create",
    "list_active",
    "find_active",
    "unblock",
    "clear_identity",
]
