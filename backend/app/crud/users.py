from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import MasterProfile, TenantProfile, User


async def get_by_username(db: AsyncSession, username: str) -> User | None:
    result = await db.execute(select(User).where(User.username == username))
    return result.scalar_one_or_none()


async def get(db: AsyncSession, user_id: UUID | str) -> User | None:
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


async def get_by_phone(db: AsyncSession, phone: str) -> tuple[User, str | None] | None:
    """Search for a user by phone in both profile tables.

    Returns (user, profile_phone) or None.
    """
    result = await db.execute(select(MasterProfile).where(MasterProfile.phone == phone))
    master_profile = result.scalar_one_or_none()
    if master_profile:
        user = await get(db, master_profile.id)
        if user:
            return user, master_profile.phone

    result = await db.execute(select(TenantProfile).where(TenantProfile.phone == phone))
    tenant_profile = result.scalar_one_or_none()
    if tenant_profile:
        user = await get(db, tenant_profile.id)
        if user:
            return user, tenant_profile.phone

    return None
