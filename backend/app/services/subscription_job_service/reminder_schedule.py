"""Timezone-aware scheduling helpers for subscription reminders.

Provides tenant-local time calculation, threshold checking, and
days-until-expiry computation, plus batched data loading.
"""

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from zoneinfo import ZoneInfo

from app.models.subscription import (
    Subscription,
    SubscriptionReminderSettings,
)
from app.models.tenant import Tenant
from app.models.tenant_settings import TenantSettings
from app.repositories import tenant_settings_repository


def is_valid_timezone(tz_name: str) -> bool:
    """Check if *tz_name* is a valid IANA timezone identifier."""
    try:
        ZoneInfo(tz_name)
        return True
    except (KeyError, TypeError, ValueError):
        return False


def is_reminder_time_ok(now_utc: datetime, reminder_time: str, tz_name: str) -> bool:
    """Return True when tenant local time is at or after *reminder_time*.

    If *tz_name* is invalid the check returns ``True`` so the caller can
    handle the decision to skip that tenant separately.
    """
    try:
        tz = ZoneInfo(tz_name)
    except (KeyError, TypeError, ValueError):
        return True  # invalid timezone — let caller skip

    local_now = now_utc.astimezone(tz)
    try:
        hour, minute = reminder_time.split(":")
        reminder = local_now.replace(
            hour=int(hour), minute=int(minute), second=0, microsecond=0
        )
        return local_now >= reminder
    except (ValueError, AttributeError):
        return True


def compute_days_until_expiry(
    expires_at: datetime,
    tz_name: str,
    now_utc: datetime | None = None,
) -> int:
    """Return days until *expires_at* using tenant-local date.

    Accepts an optional *now_utc* so callers can pass a consistent
    reference time (avoiding boundary inconsistency when multiple
    calls happen within the same function frame).

    Handles timezone-naive datetimes (e.g. from SQLite) gracefully:
    they are treated as UTC (the database convention) and converted
    to the tenant's timezone before computation.
    """
    tz = ZoneInfo(tz_name)

    if expires_at.tzinfo is not None:
        local_expiry = expires_at.astimezone(tz)
    else:
        # Naive datetime — assume UTC (database convention) and convert
        local_expiry = expires_at.replace(tzinfo=timezone.utc).astimezone(tz)

    local_today = (now_utc or datetime.now(timezone.utc)).astimezone(tz).date()
    return (local_expiry.date() - local_today).days


async def load_batched_reminder_data(
    db: AsyncSession,
    subscriptions: list[Subscription],
) -> tuple[
    dict[Any, SubscriptionReminderSettings | None],
    dict[Any, Tenant | None],
    dict[Any, TenantSettings | None],
]:
    """Load reminder settings, tenants, and tenant settings for a batch.

    Returns ``(settings_by_tenant_id, tenants_by_tenant_id, tenant_settings_by_tenant_id)``
    lookup maps.  Missing records are stored as ``None`` so callers can
    distinguish "not loaded" from "didn't exist".
    """
    tenant_ids = list({sub.tenant_id for sub in subscriptions})

    settings_map: dict[Any, SubscriptionReminderSettings | None] = {}
    if tenant_ids:
        stmt = select(SubscriptionReminderSettings).where(
            SubscriptionReminderSettings.tenant_id.in_(tenant_ids)
        )
        rows = (await db.execute(stmt)).scalars().all()
        for s in rows:
            settings_map[s.tenant_id] = s
        for tid in tenant_ids:
            settings_map.setdefault(tid, None)

    tenants_map: dict[Any, Tenant | None] = {}
    if tenant_ids:
        stmt = select(Tenant).where(Tenant.id.in_(tenant_ids))
        rows = (await db.execute(stmt)).scalars().all()
        for t in rows:
            tenants_map[t.id] = t
        for tid in tenant_ids:
            tenants_map.setdefault(tid, None)

    tenant_settings_map: dict[Any, TenantSettings | None] = {}
    if tenant_ids:
        tenant_settings_map = await tenant_settings_repository.get_settings_for_tenant_ids(
            db, tenant_ids
        )

    return settings_map, tenants_map, tenant_settings_map
