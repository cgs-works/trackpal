"""Subscription cleanup operations: expire, cancel expired, delete old.

Debt: 208 LoC (target <=200, max 240). Consolidate helpers when sub-200 gap opens.
"""

import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from zoneinfo import ZoneInfo

from app.core.database import restore_rls_context
from app.models.subscription import (
    Subscription,
    SubscriptionEvent,
    SubscriptionReminderLog,
)
from app.models.tenant import Tenant
from app.models.tenant_settings import TenantSettings


def _ensure_aware(dt: datetime) -> datetime:
    """Ensure datetime is timezone-aware; assume UTC if naive."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


async def _get_tenant_timezone_map(db: AsyncSession) -> dict[uuid.UUID, str]:
    res = await db.execute(
        select(
            TenantSettings.tenant_id,
            TenantSettings.timezone,
        )
    )
    rows = res.all()
    tz_map: dict[uuid.UUID, str] = {}
    for tenant_id, tz in rows:
        tz_map[tenant_id] = tz
    return tz_map


async def _get_tenant_end_of_day(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    now: datetime,
    today: date,
    tz_map: dict[uuid.UUID, str] | None = None,
) -> datetime:
    if tz_map is None:
        tz_map = await _get_tenant_timezone_map(db)
    tz_str = tz_map.get(tenant_id, "UTC")
    try:
        tz = ZoneInfo(tz_str)
    except (KeyError, TypeError, ValueError):
        tz = ZoneInfo("UTC")
    # Get local date from the current UTC time in tenant's timezone
    local_now = now.astimezone(tz)
    local_today = local_now.date()
    # Local end-of-day converted to UTC
    local_eod = datetime(
        local_today.year,
        local_today.month,
        local_today.day,
        23,
        59,
        59,
        tzinfo=tz,
    )
    return local_eod.astimezone(timezone.utc)


async def _expire_active_subs(
    db: AsyncSession,
    now: datetime,
    today: date,
    tz_map: dict[uuid.UUID, str] | None = None,
) -> list[dict[str, Any]]:
    if tz_map is None:
        tz_map = await _get_tenant_timezone_map(db)
    results: list[dict[str, Any]] = []
    res = await db.execute(
        select(Subscription)
        .join(Tenant, Tenant.id == Subscription.tenant_id)
        .where(
            Tenant.plan == "pro",
            Subscription.status == "active",
            Subscription.expires_at <= now,
        )
    )
    subs = list(res.scalars().all())

    for sub in subs:
        item: dict[str, Any] = {
            "id": str(sub.id),
            "action": "expire",
            "status": "success",
            "error": None,
        }
        try:
            expires_at = _ensure_aware(sub.expires_at)
            eod = await _get_tenant_end_of_day(db, sub.tenant_id, now, today, tz_map)
            if expires_at > eod:
                continue
            sub.status = "expired"
            event = SubscriptionEvent(
                tenant_id=sub.tenant_id,
                subscription_id=sub.id,
                event_type="expired",
                notes="Subscription expired automatically",
            )
            db.add(event)
            await db.flush()
        except Exception as exc:
            await db.rollback()
            item["status"] = "failed"
            item["error"] = str(exc)
        results.append(item)

    if subs:
        await db.commit()
        await restore_rls_context(db)
    return results


async def _cancel_long_expired_subs(
    db: AsyncSession, now: datetime
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    cutoff_7 = now - timedelta(days=7)
    res = await db.execute(
        select(Subscription)
        .join(Tenant, Tenant.id == Subscription.tenant_id)
        .where(
            Tenant.plan == "pro",
            Subscription.status == "expired",
            Subscription.expires_at <= cutoff_7,
        )
    )
    subs = list(res.scalars().all())

    for sub in subs:
        item: dict[str, Any] = {
            "id": str(sub.id),
            "action": "cancel_expired",
            "status": "success",
            "error": None,
        }
        try:
            expires_at = _ensure_aware(sub.expires_at)
            if expires_at > cutoff_7:
                continue
            sub.status = "cancelled"
            sub.cancelled_at = now
            event = SubscriptionEvent(
                tenant_id=sub.tenant_id,
                subscription_id=sub.id,
                event_type="cancelled",
                notes="Subscription cancelled after 7+ days expired",
            )
            db.add(event)
            await db.flush()
        except Exception as exc:
            await db.rollback()
            item["status"] = "failed"
            item["error"] = str(exc)
        results.append(item)

    if subs:
        await db.commit()
        await restore_rls_context(db)
    return results


async def _delete_old_cancelled_subs(
    db: AsyncSession, now: datetime
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    cutoff_30 = now - timedelta(days=30)
    res = await db.execute(
        select(Subscription)
        .join(Tenant, Tenant.id == Subscription.tenant_id)
        .where(
            Tenant.plan == "pro",
            Subscription.status == "cancelled",
            Subscription.cancelled_at <= cutoff_30,
        )
    )
    subs = list(res.scalars().all())

    for sub in subs:
        item: dict[str, Any] = {
            "id": str(sub.id),
            "action": "delete_cancelled",
            "status": "success",
            "error": None,
        }
        try:
            if not sub.cancelled_at:
                continue
            cancelled_at = _ensure_aware(sub.cancelled_at)
            if cancelled_at > cutoff_30:
                continue
            await db.execute(
                delete(SubscriptionEvent).where(
                    SubscriptionEvent.subscription_id == sub.id
                )
            )
            await db.execute(
                delete(SubscriptionReminderLog).where(
                    SubscriptionReminderLog.subscription_id == sub.id
                )
            )
            await db.delete(sub)
            await db.flush()
        except Exception as exc:
            await db.rollback()
            item["status"] = "failed"
            item["error"] = str(exc)
        results.append(item)

    if subs:
        await db.commit()
        await restore_rls_context(db)
    return results


async def run_cleanup(db: AsyncSession) -> list[dict[str, Any]]:
    """Run all cleanup lifecycle actions.

    1. Active subscriptions past tenant-local end-of-day → ``expired``.
    2. Subscriptions expired for 7+ days → ``cancelled``.
    3. Subscriptions cancelled for 30+ days → delete (cascade logs/events).

    Returns per-item result dicts with IDs, action, status, error (no PII).
    """
    results: list[dict[str, Any]] = []
    now = datetime.now(timezone.utc)
    today = now.date()

    results += await _expire_active_subs(
        db, now, today, tz_map=await _get_tenant_timezone_map(db)
    )
    results += await _cancel_long_expired_subs(db, now)
    results += await _delete_old_cancelled_subs(db, now)

    return results
