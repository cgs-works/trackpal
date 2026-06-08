"""Catalog repository — Service/Plan table queries."""

from uuid import UUID

from sqlalchemy import case, delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Client, Plan, Service, Subscription


async def list_services(db: AsyncSession, tenant_id: UUID) -> list[Service]:
    """List all services for a tenant, alphabetical by name."""
    result = await db.execute(
        select(Service)
        .where(Service.tenant_id == tenant_id)
        .order_by(func.lower(Service.name).asc(), Service.created_at.asc())
    )
    return list(result.scalars().all())


async def get_service(
    db: AsyncSession, tenant_id: UUID, service_id: UUID
) -> Service | None:
    """Get service by tenant and service id."""
    result = await db.execute(
        select(Service).where(Service.tenant_id == tenant_id, Service.id == service_id)
    )
    return result.scalar_one_or_none()


async def service_name_exists(
    db: AsyncSession,
    tenant_id: UUID,
    name: str,
    exclude_id: UUID | None = None,
) -> bool:
    """Check if a service name is taken within a tenant."""
    stmt = select(Service.id).where(
        Service.tenant_id == tenant_id,
        func.lower(Service.name) == name.lower(),
    )
    if exclude_id:
        stmt = stmt.where(Service.id != exclude_id)
    return (await db.execute(stmt)).first() is not None


async def list_plans(db: AsyncSession, tenant_id: UUID, service_id: UUID) -> list[Plan]:
    """List all plans for a service, alphabetical by name."""
    result = await db.execute(
        select(Plan)
        .where(Plan.tenant_id == tenant_id, Plan.service_id == service_id)
        .order_by(func.lower(Plan.name).asc(), Plan.created_at.asc())
    )
    return list(result.scalars().all())


async def get_plan(
    db: AsyncSession, tenant_id: UUID, service_id: UUID, plan_id: UUID
) -> Plan | None:
    """Get plan by tenant, service, and plan id."""
    result = await db.execute(
        select(Plan).where(
            Plan.tenant_id == tenant_id,
            Plan.service_id == service_id,
            Plan.id == plan_id,
        )
    )
    return result.scalar_one_or_none()


async def plan_name_exists(
    db: AsyncSession,
    tenant_id: UUID,
    service_id: UUID,
    name: str,
    exclude_id: UUID | None = None,
) -> bool:
    """Check if a plan name is taken within a service."""
    stmt = select(Plan.id).where(
        Plan.tenant_id == tenant_id,
        Plan.service_id == service_id,
        func.lower(Plan.name) == name.lower(),
    )
    if exclude_id:
        stmt = stmt.where(Plan.id != exclude_id)
    return (await db.execute(stmt)).first() is not None


# ── Count helpers (single-entity) ─────────────────────────────────────────


async def count_plans_for_service(
    db: AsyncSession, tenant_id: UUID, service_id: UUID
) -> int:
    """Return the number of plans for a service within a tenant."""
    result = await db.execute(
        select(func.count(Plan.id)).where(
            Plan.tenant_id == tenant_id,
            Plan.service_id == service_id,
        )
    )
    return int(result.scalar_one() or 0)


async def count_subscriptions_for_service(
    db: AsyncSession, tenant_id: UUID, service_id: UUID
) -> tuple[int, int]:
    """Return (active_count, historical_count) for all subscriptions under a service."""
    active_expr = func.sum(case((Subscription.status == "active", 1), else_=0))
    total_expr = func.count(Subscription.id)
    result = await db.execute(
        select(active_expr, total_expr).where(
            Subscription.tenant_id == tenant_id,
            Subscription.service_id == service_id,
        )
    )
    active_count, total_count = result.one()
    active = int(active_count or 0)
    total = int(total_count or 0)
    return active, total - active


async def count_subscriptions_for_plan(
    db: AsyncSession, tenant_id: UUID, service_id: UUID, plan_id: UUID
) -> tuple[int, int]:
    """Return (active_count, historical_count) for all subscriptions under a plan."""
    active_expr = func.sum(case((Subscription.status == "active", 1), else_=0))
    total_expr = func.count(Subscription.id)
    result = await db.execute(
        select(active_expr, total_expr).where(
            Subscription.tenant_id == tenant_id,
            Subscription.service_id == service_id,
            Subscription.plan_id == plan_id,
        )
    )
    active_count, total_count = result.one()
    active = int(active_count or 0)
    total = int(total_count or 0)
    return active, total - active


# ── Aggregate summary helpers (N+1 prevention) ────────────────────────────


async def count_plans_for_services(
    db: AsyncSession, tenant_id: UUID
) -> dict[UUID, int]:
    """Return a dict mapping service_id -> plan_count for all services in a tenant (1 query)."""
    result = await db.execute(
        select(Plan.service_id, func.count(Plan.id))
        .where(Plan.tenant_id == tenant_id)
        .group_by(Plan.service_id)
    )
    return {service_id: int(count) for service_id, count in result.all()}


async def count_subscriptions_for_all_services(
    db: AsyncSession, tenant_id: UUID
) -> dict[UUID, tuple[int, int]]:
    """Return a dict mapping service_id -> (active_count, historical_count) for all services (1 query)."""
    active_expr = func.sum(case((Subscription.status == "active", 1), else_=0))
    total_expr = func.count(Subscription.id)
    result = await db.execute(
        select(Subscription.service_id, active_expr, total_expr)
        .where(Subscription.tenant_id == tenant_id)
        .group_by(Subscription.service_id)
    )
    mapping: dict[UUID, tuple[int, int]] = {}
    for service_id, active_count, total_count in result.all():
        active = int(active_count or 0)
        total = int(total_count or 0)
        mapping[service_id] = (active, total - active)
    return mapping


async def count_subscriptions_for_all_plans(
    db: AsyncSession, tenant_id: UUID, service_id: UUID
) -> dict[UUID, tuple[int, int]]:
    """Return a dict mapping plan_id -> (active_count, historical_count) for all plans in a service (1 query)."""
    active_expr = func.sum(case((Subscription.status == "active", 1), else_=0))
    total_expr = func.count(Subscription.id)
    result = await db.execute(
        select(Subscription.plan_id, active_expr, total_expr)
        .where(
            Subscription.tenant_id == tenant_id,
            Subscription.service_id == service_id,
        )
        .group_by(Subscription.plan_id)
    )
    mapping: dict[UUID, tuple[int, int]] = {}
    for plan_id, active_count, total_count in result.all():
        active = int(active_count or 0)
        total = int(total_count or 0)
        mapping[plan_id] = (active, total - active)
    return mapping


# ── Active subscription row helpers ────────────────────────────────────────


async def list_active_subscription_rows_for_service(
    db: AsyncSession, tenant_id: UUID, service_id: UUID, *, offset: int, limit: int
) -> list[tuple[Subscription, Client, Service, Plan]]:
    """List active subscription rows (with joined client/service/plan) for a service, ordered by expiration."""
    result = await db.execute(
        select(Subscription, Client, Service, Plan)
        .join(Client, Client.id == Subscription.client_id)
        .join(Service, Service.id == Subscription.service_id)
        .join(Plan, Plan.id == Subscription.plan_id)
        .where(
            Subscription.tenant_id == tenant_id,
            Subscription.service_id == service_id,
            Subscription.status == "active",
        )
        .order_by(
            Subscription.expires_at.is_(None).asc(),
            Subscription.expires_at.asc(),
            Subscription.created_at.asc(),
        )
        .offset(offset)
        .limit(limit)
    )
    return list(result.all())


async def list_active_subscription_rows_for_plan(
    db: AsyncSession,
    tenant_id: UUID,
    service_id: UUID,
    plan_id: UUID,
    *,
    offset: int,
    limit: int,
) -> list[tuple[Subscription, Client, Service, Plan]]:
    """List active subscription rows (with joins) for a plan, ordered by expiration."""
    result = await db.execute(
        select(Subscription, Client, Service, Plan)
        .join(Client, Client.id == Subscription.client_id)
        .join(Service, Service.id == Subscription.service_id)
        .join(Plan, Plan.id == Subscription.plan_id)
        .where(
            Subscription.tenant_id == tenant_id,
            Subscription.service_id == service_id,
            Subscription.plan_id == plan_id,
            Subscription.status == "active",
        )
        .order_by(
            Subscription.expires_at.is_(None).asc(),
            Subscription.expires_at.asc(),
            Subscription.created_at.asc(),
        )
        .offset(offset)
        .limit(limit)
    )
    return list(result.all())


# ── Cascade delete helpers ─────────────────────────────────────────────────


async def delete_subscriptions_for_service(
    db: AsyncSession, tenant_id: UUID, service_id: UUID
) -> None:
    """Delete all subscriptions under a service within a tenant."""
    await db.execute(
        delete(Subscription).where(
            Subscription.tenant_id == tenant_id,
            Subscription.service_id == service_id,
        )
    )


async def delete_subscriptions_for_plan(
    db: AsyncSession, tenant_id: UUID, service_id: UUID, plan_id: UUID
) -> None:
    """Delete all subscriptions under a plan within a tenant."""
    await db.execute(
        delete(Subscription).where(
            Subscription.tenant_id == tenant_id,
            Subscription.service_id == service_id,
            Subscription.plan_id == plan_id,
        )
    )


async def delete_plans_for_service(
    db: AsyncSession, tenant_id: UUID, service_id: UUID
) -> None:
    """Delete all plans for a service within a tenant."""
    await db.execute(
        delete(Plan).where(
            Plan.tenant_id == tenant_id,
            Plan.service_id == service_id,
        )
    )


__all__ = [
    "list_services",
    "get_service",
    "service_name_exists",
    "list_plans",
    "get_plan",
    "plan_name_exists",
    "count_plans_for_service",
    "count_subscriptions_for_service",
    "count_subscriptions_for_plan",
    "count_plans_for_services",
    "count_subscriptions_for_all_services",
    "count_subscriptions_for_all_plans",
    "list_active_subscription_rows_for_service",
    "list_active_subscription_rows_for_plan",
    "delete_subscriptions_for_service",
    "delete_subscriptions_for_plan",
    "delete_plans_for_service",
]
