"""Tenant repository — tenant table queries."""

import uuid
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.phone import normalize_phone
from app.models import DemoTenantStatus, Tenant
from app.repositories import tenant_settings_repository


async def resolve_locale(db: AsyncSession, tenant_id: UUID) -> str:
    return await tenant_settings_repository.resolve_locale(db, tenant_id)


async def get(db: AsyncSession, tenant_id: UUID) -> Tenant | None:
    """Get tenant by id (with owner)."""
    result = await db.execute(
        select(Tenant).options(selectinload(Tenant.owner)).where(Tenant.id == tenant_id)
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


async def get_active_by_owner(db: AsyncSession, owner_user_id: UUID) -> Tenant | None:
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
    """Get all production tenants ordered by creation time with summary stats."""
    result = await db.execute(
        select(Tenant)
        .options(selectinload(Tenant.owner))
        .where(Tenant.is_demo.is_(False))
        .order_by(Tenant.created_at.desc())
    )
    profiles = list(result.scalars().all())
    total = len(profiles)
    active = sum(1 for p in profiles if p.is_active)
    inactive = total - active
    return profiles, {"total": total, "active": active, "inactive": inactive}


async def get_demos(
    db: AsyncSession,
    *,
    status: DemoTenantStatus | None = None,
    now: datetime | None = None,
) -> list[Tenant]:
    """List Demo Tenants, optionally filtering their derived lifecycle status."""
    stmt = (
        select(Tenant)
        .options(selectinload(Tenant.owner))
        .where(Tenant.is_demo.is_(True))
        .order_by(Tenant.created_at.desc())
    )

    if status is not None:
        current_time = now or datetime.now(timezone.utc)
        if status is DemoTenantStatus.PENDING:
            stmt = stmt.where(Tenant.demo_activated_at.is_(None))
        elif status is DemoTenantStatus.ACTIVE:
            stmt = stmt.where(
                Tenant.demo_activated_at.is_not(None),
                Tenant.demo_expires_at > current_time,
            )
        elif status is DemoTenantStatus.EXPIRED:
            stmt = stmt.where(Tenant.demo_expires_at <= current_time)

    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_demo(db: AsyncSession, tenant_id: UUID) -> Tenant | None:
    """Get a Demo Tenant by id without matching production Tenants."""
    result = await db.execute(
        select(Tenant)
        .options(selectinload(Tenant.owner))
        .where(Tenant.id == tenant_id, Tenant.is_demo.is_(True))
    )
    return result.scalar_one_or_none()


async def get_expired_demos(
    db: AsyncSession, *, now: datetime | None = None
) -> list[Tenant]:
    """Find Demo Tenants whose persisted expiration has passed."""
    return await get_demos(db, status=DemoTenantStatus.EXPIRED, now=now)


async def get_by_id_or_owner(db: AsyncSession, tenant_id: UUID) -> Tenant | None:
    """Get tenant by id or owner user id (with owner loaded)."""
    result = await db.execute(
        select(Tenant)
        .options(selectinload(Tenant.owner))
        .where((Tenant.id == tenant_id) | (Tenant.owner_user_id == tenant_id))
    )
    return result.scalar_one_or_none()


async def get_stats(db: AsyncSession) -> dict:
    """Get production tenant stats, excluding Demo Tenants."""
    total = await db.execute(
        select(func.count()).select_from(Tenant).where(Tenant.is_demo.is_(False))
    )
    active = await db.execute(
        select(func.count())
        .select_from(Tenant)
        .where(Tenant.is_demo.is_(False), Tenant.is_active)
    )
    t = total.scalar_one()
    a = active.scalar_one()
    return {"total": t, "active": a, "inactive": t - a}


async def resolve_locale_by_owner(db: AsyncSession, owner_user_id: UUID) -> str:
    return await tenant_settings_repository.resolve_locale_by_owner(db, owner_user_id)


async def resolve_locale_by_client(db: AsyncSession, client_owner_user_id: UUID) -> str:
    return await tenant_settings_repository.resolve_locale_by_client(
        db, client_owner_user_id
    )


def _instance_aliases(instance_name: str) -> tuple[str, ...]:
    raw = (instance_name or "").strip()
    if not raw:
        return ()

    aliases = {raw}
    if raw.startswith("tenant-"):
        aliases.add(raw.removeprefix("tenant-"))
    else:
        aliases.add(f"tenant-{raw}")

    return tuple(alias for alias in aliases if alias)


async def get_by_instance(db: AsyncSession, instance_name: str) -> Tenant | None:
    """Get tenant by Evolution instance name, accepting tenant-* aliases."""
    aliases = _instance_aliases(instance_name)
    if not aliases:
        return None

    result = await db.execute(
        select(Tenant)
        .options(selectinload(Tenant.owner))
        .where(Tenant.evolution_instance_name.in_(aliases))
    )
    return result.scalar_one_or_none()


async def get_by_whatsapp_lid(db: AsyncSession, lid: str) -> Tenant | None:
    """Get active tenant by whatsapp_lid."""
    result = await db.execute(
        select(Tenant)
        .options(selectinload(Tenant.owner))
        .where(Tenant.whatsapp_lid == lid, Tenant.is_active)
    )
    return result.scalar_one_or_none()


async def get_active_by_whatsapp_identity(
    db: AsyncSession,
    *,
    phone_digits: str | None = None,
    whatsapp_lid: str | None = None,
) -> Tenant | None:
    """Get an active tenant by WhatsApp phone or LID identity.

    Phone matching accepts both canonical digits-only values and legacy
    `+`-prefixed values stored in the database.
    """
    phone_norm = normalize_phone(phone_digits) if phone_digits else None
    lid = (whatsapp_lid or "").strip() or None

    if not phone_norm and not lid:
        return None

    stmt = select(Tenant).options(selectinload(Tenant.owner)).where(Tenant.is_active)

    phone_variants = [phone_norm, f"+{phone_norm}"] if phone_norm else []
    if phone_variants and lid:
        stmt = stmt.where(
            or_(
                Tenant.whatsapp_phone.in_(phone_variants),
                Tenant.whatsapp_lid == lid,
            )
        )
    elif phone_variants:
        stmt = stmt.where(Tenant.whatsapp_phone.in_(phone_variants))
    else:
        stmt = stmt.where(Tenant.whatsapp_lid == lid)

    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def update_tenant_lid(db: AsyncSession, tenant_id: uuid.UUID, lid: str) -> None:
    """Persist whatsapp_lid on a tenant (progressive fill)."""
    result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    tenant = result.scalar_one_or_none()
    if tenant and not tenant.whatsapp_lid:
        tenant.whatsapp_lid = lid
        await db.commit()


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
    "get_demos",
    "get_demo",
    "get_expired_demos",
    "get_by_id_or_owner",
    "get_stats",
    "resolve_locale_by_owner",
    "resolve_locale_by_client",
    "client_prefix_exists",
    "get_by_instance",
    "get_by_whatsapp_lid",
    "update_tenant_lid",
    "get_active_by_whatsapp_identity",
]
