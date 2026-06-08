"""Profile repository — MasterProfile/Tenant/Client profile queries."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Client, MasterProfile, Tenant


async def get_master_profile(db: AsyncSession, user_id: UUID) -> MasterProfile | None:
    """Get master profile by user id."""
    result = await db.execute(select(MasterProfile).where(MasterProfile.id == user_id))
    return result.scalar_one_or_none()


async def get_tenant_profile(db: AsyncSession, user_id: UUID) -> Tenant | None:
    """Get tenant profile by owner user id."""
    result = await db.execute(select(Tenant).where(Tenant.owner_user_id == user_id))
    return result.scalar_one_or_none()


async def get_client_profile(db: AsyncSession, user_id: UUID) -> Client | None:
    """Get client profile by owner user id, with tenant and user loaded."""
    result = await db.execute(
        select(Client)
        .options(selectinload(Client.tenant), selectinload(Client.user))
        .where(Client.owner_user_id == user_id)
    )
    return result.scalar_one_or_none()


__all__ = [
    "get_master_profile",
    "get_tenant_profile",
    "get_client_profile",
]
