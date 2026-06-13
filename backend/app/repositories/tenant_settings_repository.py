"""TenantSettings repository — queries for the tenant_settings table."""

import uuid
from collections.abc import Iterable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Client, Tenant, TenantSettings


async def get_by_tenant_id(
    db: AsyncSession, tenant_id: uuid.UUID
) -> TenantSettings | None:
    result = await db.execute(
        select(TenantSettings).where(TenantSettings.tenant_id == tenant_id)
    )
    return result.scalar_one_or_none()


async def get_or_create_by_tenant_id(
    db: AsyncSession, tenant_id: uuid.UUID
) -> tuple[TenantSettings, bool]:
    settings = await get_by_tenant_id(db, tenant_id)
    if settings is not None:
        return settings, False

    settings = TenantSettings(tenant_id=tenant_id, locale="en", timezone="UTC")
    db.add(settings)
    await db.flush()
    return settings, True


async def update_settings(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    values: dict[str, object],
) -> TenantSettings:
    settings, _created = await get_or_create_by_tenant_id(db, tenant_id)
    for field in ("locale", "timezone"):
        if field in values:
            setattr(settings, field, values[field])
    await db.flush()
    return settings


async def resolve_locale(db: AsyncSession, tenant_id: uuid.UUID) -> str:
    result = await db.execute(
        select(TenantSettings.locale).where(TenantSettings.tenant_id == tenant_id)
    )
    row = result.scalar_one_or_none()
    return row or "en"


async def resolve_locale_by_owner(db: AsyncSession, owner_user_id: uuid.UUID) -> str:
    result = await db.execute(
        select(TenantSettings.locale)
        .select_from(Tenant)
        .join(TenantSettings, TenantSettings.tenant_id == Tenant.id)
        .where(Tenant.owner_user_id == owner_user_id)
    )
    row = result.scalar_one_or_none()
    return row or "en"


async def resolve_locale_by_client(
    db: AsyncSession, client_owner_user_id: uuid.UUID
) -> str:
    result = await db.execute(
        select(TenantSettings.locale)
        .select_from(Client)
        .join(TenantSettings, TenantSettings.tenant_id == Client.tenant_id)
        .where(Client.owner_user_id == client_owner_user_id)
    )
    row = result.scalar_one_or_none()
    return row or "en"


async def resolve_timezone(db: AsyncSession, tenant_id: uuid.UUID) -> str:
    result = await db.execute(
        select(TenantSettings.timezone).where(TenantSettings.tenant_id == tenant_id)
    )
    row = result.scalar_one_or_none()
    return row or "UTC"


async def get_settings_for_tenant_ids(
    db: AsyncSession, tenant_ids: Iterable[uuid.UUID]
) -> dict[uuid.UUID, TenantSettings | None]:
    ids = list(set(tenant_ids))
    settings_map: dict[uuid.UUID, TenantSettings | None] = {
        tenant_id: None for tenant_id in ids
    }
    if not ids:
        return settings_map

    result = await db.execute(
        select(TenantSettings).where(TenantSettings.tenant_id.in_(ids))
    )
    for settings in result.scalars().all():
        settings_map[settings.tenant_id] = settings
    return settings_map
