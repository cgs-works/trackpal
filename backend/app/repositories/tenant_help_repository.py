from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import TenantHelpAcknowledgement


async def get_acknowledgement(
    db: AsyncSession, tenant_id: UUID, release_id: str
) -> TenantHelpAcknowledgement | None:
    result = await db.execute(
        select(TenantHelpAcknowledgement).where(
            TenantHelpAcknowledgement.tenant_id == tenant_id,
            TenantHelpAcknowledgement.release_id == release_id,
        )
    )
    return result.scalar_one_or_none()


async def acknowledge(
    db: AsyncSession,
    tenant_id: UUID,
    release_id: str,
    status: str,
) -> TenantHelpAcknowledgement:
    existing = await get_acknowledgement(db, tenant_id, release_id)
    if existing is not None:
        return existing

    acknowledgement = TenantHelpAcknowledgement(
        tenant_id=tenant_id,
        release_id=release_id,
        status=status,
        acknowledged_at=datetime.now(timezone.utc),
    )
    db.add(acknowledgement)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        existing = await get_acknowledgement(db, tenant_id, release_id)
        if existing is not None:
            return existing
        raise
    await db.refresh(acknowledgement)
    return acknowledgement
