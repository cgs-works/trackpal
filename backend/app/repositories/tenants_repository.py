"""Tenant repository — tenant table queries."""

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Client, Tenant


async def resolve_locale(db: AsyncSession, tenant_id: UUID) -> str:
    """Resolve tenant locale, defaulting to ``"en"``."""
    result = await db.execute(
        select(Tenant.locale).where(Tenant.id == tenant_id)
    )
    row = result.scalar_one_or_none()
    return row if row else "en"


async def get(db: AsyncSession, tenant_id: UUID) -> Tenant | None:
    """Get tenant by id (with owner)."""
    result = await db.execute(
        select(Tenant)
        .options(selectinload(Tenant.owner))
        .where(Tenant.id == tenant_id)
    )
    return result.scalar_one_or_none()


async def get_by_owner(db: AsyncSession, owner_user_id: UUID) -> Tenant | None:
    """Get tenant by owner user id (with owner)."""
    result = await db.execute(
        select(Tenant)
        .options(selectinload(Tenant.owner))
        .where(Tenant.owner_user_id == owner_user_id)
    )
    return result.scalar_one_or_none()


async def get_active_by_owner(
    db: AsyncSession, owner_user_id: UUID
) -> Tenant | None:
    """Get active tenant for a given owner."""
    result = await db.execute(
        select(Tenant)
        .options(selectinload(Tenant.owner))
        .where(Tenant.owner_user_id == owner_user_id, Tenant.is_active)
    )
    return result.scalar_one_or_none()


async def get_active(db: AsyncSession, tenant_id: UUID) -> Tenant | None:
    """Get tenant by id that is active."""
    result = await db.execute(
        select(Tenant).where(Tenant.id == tenant_id, Tenant.is_active)
    )
    return result.scalar_one_or_none()


async def get_all(db: AsyncSession) -> tuple[list[Tenant], dict]:
    """Get all tenants ordered by creation time with summary stats."""
    result = await db.execute(
        select(Tenant)
        .options(selectinload(Tenant.owner))
        .order_by(Tenant.created_at.desc())
    )
    profiles = list(result.scalars().all())
    total = len(profiles)
    active = sum(1 for p in profiles if p.is_active)
    inactive = total - active
    return profiles, {"total": total, "active": active, "inactive": inactive}


async def get_by_id_or_owner(
    db: AsyncSession, tenant_id: UUID
) -> Tenant | None:
    """Get tenant by id or owner user id (with owner loaded)."""
    result = await db.execute(
        select(Tenant)
        .options(selectinload(Tenant.owner))
        .where((Tenant.id == tenant_id) | (Tenant.owner_user_id == tenant_id))
    )
    return result.scalar_one_or_none()


async def get_stats(db: AsyncSession) -> dict:
    """Get tenant stats: total, active, inactive counts."""
    total = await db.execute(select(func.count()).select_from(Tenant))
    active = await db.execute(
        select(func.count()).select_from(Tenant).where(Tenant.is_active)
    )
    t = total.scalar_one()
    a = active.scalar_one()
    return {"total": t, "active": a, "inactive": t - a}


async def resolve_locale_by_owner(
    db: AsyncSession, owner_user_id: UUID
) -> str:
    """Resolve tenant locale by owner user id, defaulting to ``"en"``."""
    result = await db.execute(
        select(Tenant.locale).where(Tenant.owner_user_id == owner_user_id)
    )
    row = result.scalar_one_or_none()
    return row if row else "en"


async def resolve_locale_by_client(
    db: AsyncSession, client_owner_user_id: UUID
) -> str:
    """Resolve tenant locale from a client owner user id."""
    result = await db.execute(
        select(Tenant.locale)
        .select_from(Client)
        .join(Tenant, Client.tenant_id == Tenant.id)
        .where(Client.owner_user_id == client_owner_user_id)
    )
    row = result.scalar_one_or_none()
    return row if row else "en"


async def client_prefix_exists(
    db: AsyncSession,
    client_prefix: str,
    exclude_tenant_id: UUID | None = None,
) -> bool:
    """Check if a client prefix is already taken."""
    stmt = select(Tenant.id).where(
        func.lower(Tenant.client_prefix) == client_prefix.lower()
    )
    if exclude_tenant_id is not None:
        stmt = stmt.where(Tenant.id != exclude_tenant_id)
    return (await db.execute(stmt)).first() is not None


__all__ = [
    "resolve_locale",
    "get",
    "get_by_owner",
    "get_active_by_owner",
    "get_active",
    "get_all",
    "get_by_id_or_owner",
    "get_stats",
    "resolve_locale_by_owner",
    "resolve_locale_by_client",
    "client_prefix_exists",
]
