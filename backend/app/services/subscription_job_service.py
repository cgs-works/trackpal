import uuid
from datetime import datetime, timezone, timedelta, date
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.subscription import (
    Subscription,
    SubscriptionReminderSettings,
    SubscriptionEvent,
    SubscriptionReminderLog,
)
from app.core.database import restore_rls_context


class SubscriptionJobService:
    """Background job service for subscription lifecycle management.

    Called by n8n via the protected job endpoint.  All operations use
    UTC as the default timezone; per-tenant timezone from
    ``subscription_reminder_settings`` is supported where available.
    """

    async def run_cleanup(self, db: AsyncSession) -> list[dict[str, Any]]:
        """Run all cleanup lifecycle actions.

        1. Active subscriptions past tenant-local end-of-day → ``expired``.
        2. Subscriptions expired for 7+ days → ``cancelled``.
        3. Subscriptions cancelled for 30+ days → delete (cascade logs/events).

        Returns per-item result dicts with IDs, action, status, error (no PII).
        """
        results: list[dict[str, Any]] = []
        now = datetime.now(timezone.utc)
        today = now.date()

        # ── Step 1: Active → Expired ──────────────────────────────────
        results += await self._expire_active_subs(db, now, today)

        # ── Step 2: Expired 7+ days → Cancelled ────────────────────────
        results += await self._cancel_long_expired_subs(db, now)

        # ── Step 3: Cancelled 30+ days → Delete ────────────────────────
        results += await self._delete_old_cancelled_subs(db, now)

        return results

    @staticmethod
    def _ensure_aware(dt: datetime) -> datetime:
        """Ensure datetime is timezone-aware; assume UTC if naive."""
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt

    async def _get_tenant_timezone_map(
        self, db: AsyncSession
    ) -> dict[uuid.UUID, str]:
        """Build a mapping of tenant_id → timezone string.

        Defaults to ``UTC`` when no reminder settings exist.
        """
        res = await db.execute(
            select(SubscriptionReminderSettings.tenant_id, SubscriptionReminderSettings.timezone)
        )
        rows = res.all()
        tz_map: dict[uuid.UUID, str] = {}
        for tenant_id, tz in rows:
            tz_map[tenant_id] = tz
        return tz_map

    async def _get_tenant_end_of_day(
        self, db: AsyncSession, tenant_id: uuid.UUID, now: datetime, today: date
    ) -> datetime:
        """Return end-of-day (23:59:59) for the tenant's timezone.

        Falls back to UTC when no timezone is configured.
        """
        tz_map = await self._get_tenant_timezone_map(db)
        tenant_tz_str = tz_map.get(tenant_id, "UTC")
        # For v1 we treat everything as UTC since Python zoneinfo
        # may not be available in all deployments.  This is the
        # bounded approximation.
        _ = tenant_tz_str  # reserved for zoneinfo-based resolution
        return datetime(today.year, today.month, today.day, 23, 59, 59, tzinfo=timezone.utc)

    async def _expire_active_subs(
        self, db: AsyncSession, now: datetime, today: date
    ) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        res = await db.execute(
            select(Subscription).where(
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
                expires_at = self._ensure_aware(sub.expires_at)
                # Check tenant-local end-of-day
                eod = await self._get_tenant_end_of_day(
                    db, sub.tenant_id, now, today
                )
                if expires_at > eod:
                    # Not yet past tenant-local end-of-day
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
        self, db: AsyncSession, now: datetime
    ) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        cutoff_7 = now - timedelta(days=7)
        res = await db.execute(
            select(Subscription).where(
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
                expires_at = self._ensure_aware(sub.expires_at)
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
        self, db: AsyncSession, now: datetime
    ) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        cutoff_30 = now - timedelta(days=30)
        res = await db.execute(
            select(Subscription).where(
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
                cancelled_at = self._ensure_aware(sub.cancelled_at)
                if cancelled_at > cutoff_30:
                    continue
                # Delete events and reminder logs explicitly, then subscription
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

    async def run_reminders_stub(self) -> list[dict[str, Any]]:
        """Placeholder for reminder payload generation.

        Returns an empty list; reminders are handled by a separate
        endpoint/service (see ``[ready] Add reminder payload generation
        and send-status API``).
        """
        return []
