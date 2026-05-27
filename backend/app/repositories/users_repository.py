"""User repository — direct user table queries."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.phone import normalize_phone
from app.models import MasterProfile, Tenant, User


async def get_by_username(db: AsyncSession, username: str) -> User | None:
    """Look up user by username (case-sensitive)."""
    result = await db.execute(select(User).where(User.username == username))
    return result.scalar_one_or_none()


async def get(db: AsyncSession, user_id: UUID | str) -> User | None:
    """Look up user by primary key."""
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


async def get_by_phone(db: AsyncSession, phone: str) -> tuple[User, str | None] | None:
    """Look up a user by phone across MasterProfile and Tenant profiles.

    Normalizes input to digits-only, then searches for both canonical and
    ``+``-prefixed variants for backward-compatibility with pre-migration data.
    Returns ``(user, profile_phone)`` or ``None``.
    """
    canonical = normalize_phone(phone)
    if canonical is None:
        return None

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


async def get_by_lid(db: AsyncSession, lid: str) -> tuple[User, str] | None:
    """Look up a user by WhatsApp LID across MasterProfile and Tenant.

    Returns ``(user, role_label)`` or ``None``.
    Role label is one of ``"master"`` or ``"tenant"``.
    """
    # Check master profile
    result = await db.execute(
        select(MasterProfile).where(MasterProfile.whatsapp_lid == lid)
    )
    master_profile = result.scalar_one_or_none()
    if master_profile:
        user = await get(db, master_profile.id)
        if user:
            return user, "master"

    # Check tenant
    result = await db.execute(select(Tenant).where(Tenant.whatsapp_lid == lid))
    tenant = result.scalar_one_or_none()
    if tenant:
        user = await get(db, tenant.owner_user_id)
        if user:
            return user, "tenant"

    return None


async def update_master_lid(db: AsyncSession, user_id: UUID, lid: str) -> None:
    """Persist whatsapp_lid on a master profile (progressive fill)."""
    result = await db.execute(select(MasterProfile).where(MasterProfile.id == user_id))
    profile = result.scalar_one_or_none()
    if profile and not profile.whatsapp_lid:
        profile.whatsapp_lid = lid
        await db.commit()


async def username_exists(
    db: AsyncSession, username: str, exclude_user_id: UUID | None = None
) -> bool:
    """Check if a username is already taken, optionally excluding a given user id."""
    stmt = select(User.id).where(User.username == username)
    if exclude_user_id is not None:
        stmt = stmt.where(User.id != exclude_user_id)
    return (await db.execute(stmt)).first() is not None


# re-export module-level shim name (same interface as old app.crud.users)
__all__ = [
    "get",
    "get_by_username",
    "get_by_phone",
    "get_by_lid",
    "update_master_lid",
    "username_exists",
]
