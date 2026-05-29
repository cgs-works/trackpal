"""Repository for code-service global status and tenant selections."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.code_service_global_status import CodeServiceGlobalStatus
from app.models.tenant_code_service_selection import TenantCodeServiceSelection


# ── Global status ────────────────────────────────────────────────────────


async def get_all_global(db: AsyncSession) -> list[CodeServiceGlobalStatus]:
    """Return all global status rows (ordered by service_key)."""
    result = await db.execute(
        select(CodeServiceGlobalStatus).order_by(CodeServiceGlobalStatus.service_key)
    )
    return list(result.scalars().all())


async def set_global_active(
    db: AsyncSession, service_key: str, is_active: bool
) -> CodeServiceGlobalStatus:
    """Upsert global active status for a service key."""
    existing = await db.get(CodeServiceGlobalStatus, service_key)
    if existing is not None:
        existing.is_active = is_active
        return existing
    row = CodeServiceGlobalStatus(service_key=service_key, is_active=is_active)
    db.add(row)
    await db.flush()
    return row


async def get_active_global_keys(db: AsyncSession) -> set[str]:
    """Return the set of globally active service keys."""
    result = await db.execute(
        select(CodeServiceGlobalStatus.service_key).where(
            CodeServiceGlobalStatus.is_active.is_(True)
        )
    )
    return {row[0] for row in result.all()}


# ── Tenant selections ────────────────────────────────────────────────────


async def get_tenant_selections(
    db: AsyncSession, tenant_id: UUID
) -> list[TenantCodeServiceSelection]:
    """Return all selection rows for a tenant (ordered by service_key)."""
    result = await db.execute(
        select(TenantCodeServiceSelection)
        .where(TenantCodeServiceSelection.tenant_id == tenant_id)
        .order_by(TenantCodeServiceSelection.service_key)
    )
    return list(result.scalars().all())


async def get_tenant_selected_keys(db: AsyncSession, tenant_id: UUID) -> set[str]:
    """Return the set of service keys selected by a tenant."""
    result = await db.execute(
        select(TenantCodeServiceSelection.service_key).where(
            TenantCodeServiceSelection.tenant_id == tenant_id
        )
    )
    return {row[0] for row in result.all()}


async def replace_tenant_selections(
    db: AsyncSession, tenant_id: UUID, service_keys: list[str]
) -> None:
    """Full-replace sync: delete all existing + insert new set.

    Runs in the caller's transaction (single commit boundary).
    """
    await db.execute(
        delete(TenantCodeServiceSelection).where(
            TenantCodeServiceSelection.tenant_id == tenant_id
        )
    )
    for key in service_keys:
        db.add(TenantCodeServiceSelection(tenant_id=tenant_id, service_key=key))
    await db.flush()


async def get_effective_service_keys(db: AsyncSession, tenant_id: UUID) -> list[str]:
    """Effective list = tenant_selected ∩ global_active, sorted A-Z."""
    tenant_keys = await get_tenant_selected_keys(db, tenant_id)
    global_keys = await get_active_global_keys(db)
    effective = sorted(tenant_keys & global_keys)
    return effective
