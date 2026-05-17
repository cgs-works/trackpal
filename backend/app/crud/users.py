from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.phone import normalize_phone
from app.models import MasterProfile, Tenant, User


async def get_by_username(db: AsyncSession, username: str) -> User | None:
    result = await db.execute(select(User).where(User.username == username))
    return result.scalar_one_or_none()


async def get(db: AsyncSession, user_id: UUID | str) -> User | None:
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


async def get_by_phone(db: AsyncSession, phone: str) -> tuple[User, str | None] | None:
    """Search for a user by phone in both profile tables.

    Normalizes the input phone to canonical digits-only form before lookup.
    Also searches for ``+``-prefixed variant for backward compatibility
    with pre-migration data.

    Returns (user, profile_phone) or None.
    """
    canonical = normalize_phone(phone)
    if canonical is None:
        return None

    # Search for both canonical and +-prefixed variants to handle
    # pre-migration data that still has + prefix.
    variants = [canonical, f"+{canonical}"]

    result = await db.execute(
        select(MasterProfile).where(MasterProfile.phone.in_(variants))
    )
    master_profile = result.scalar_one_or_none()
    if master_profile:
        user = await get(db, master_profile.id)
        if user:
            return user, master_profile.phone

    result = await db.execute(select(Tenant).where(Tenant.whatsapp_phone.in_(variants)))
    tenant = result.scalar_one_or_none()
    if tenant:
        user = await get(db, tenant.owner_user_id)
        if user:
            return user, tenant.whatsapp_phone

    return None
