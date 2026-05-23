import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import restore_rls_context
from app.core.i18n import t as i18n_t
from app.models.subscription import (
    Subscription,
    SubscriptionEvent,
    SubscriptionReminderLog,
    SubscriptionReminderSettings,
)
from app.models.tenant import Tenant


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

        results += await self._expire_active_subs(db, now, today)
        results += await self._cancel_long_expired_subs(db, now)
        results += await self._delete_old_cancelled_subs(db, now)

        return results

    @staticmethod
    def _ensure_aware(dt: datetime) -> datetime:
        """Ensure datetime is timezone-aware; assume UTC if naive."""
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt

    async def _get_tenant_timezone_map(self, db: AsyncSession) -> dict[uuid.UUID, str]:
        res = await db.execute(
            select(
                SubscriptionReminderSettings.tenant_id,
                SubscriptionReminderSettings.timezone,
            )
        )
        rows = res.all()
        tz_map: dict[uuid.UUID, str] = {}
        for tenant_id, tz in rows:
            tz_map[tenant_id] = tz
        return tz_map

    async def _get_tenant_end_of_day(
        self, db: AsyncSession, tenant_id: uuid.UUID, now: datetime, today: date
    ) -> datetime:
        tz_map = await self._get_tenant_timezone_map(db)
        tenant_tz_str = tz_map.get(tenant_id, "UTC")
        _ = tenant_tz_str
        return datetime(
            today.year, today.month, today.day, 23, 59, 59, tzinfo=timezone.utc
        )

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
                eod = await self._get_tenant_end_of_day(db, sub.tenant_id, now, today)
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

    # ------------------------------------------------------------------
    # Reminder payload generation
    # ------------------------------------------------------------------

    async def generate_reminder_payloads(
        self, db: AsyncSession, cursor: str | None = None, page_size: int = 100
    ) -> dict[str, Any]:
        """Generate pending reminder payloads for active subscriptions.

        Returns dict with ``items`` (list of payload dicts) and optional
        ``next_cursor`` for opaque pagination.

        Creates ``SubscriptionReminderLog`` entries for each payload with
        status ``pending``.  Dedupes by unique constraint on
        (subscription_id, days_before_expiry, sent_for_date, recipient_type).
        """
        now = datetime.now(timezone.utc)
        today = now.date()

        stmt = (
            select(Subscription)
            .options(
                selectinload(Subscription.client),
                selectinload(Subscription.service),
                selectinload(Subscription.plan),
            )
            .where(
                Subscription.status == "active",
                Subscription.expires_at > now,
            )
            .order_by(Subscription.expires_at.asc())
        )

        if cursor:
            try:
                cursor_dt = datetime.fromisoformat(cursor)
                if cursor_dt.tzinfo is None:
                    cursor_dt = cursor_dt.replace(tzinfo=timezone.utc)
                stmt = stmt.where(Subscription.expires_at > cursor_dt)
            except (ValueError, TypeError):
                pass

        res = await db.execute(stmt.limit(page_size + 1))
        subs = list(res.unique().scalars().all())

        has_more = len(subs) > page_size
        if has_more:
            subs = subs[:page_size]

        items: list[dict[str, Any]] = []

        for sub in subs:
            try:
                settings_res = await db.execute(
                    select(SubscriptionReminderSettings).where(
                        SubscriptionReminderSettings.tenant_id == sub.tenant_id
                    )
                )
                settings = settings_res.scalar_one_or_none()

                reminder_time = settings.reminder_time if settings else "09:00"
                warning_days = settings.warning_days if settings else [7, 3, 1]
                recipient_mode = settings.recipient_mode if settings else "tenant_only"

                if not self._is_reminder_time_ok(now, reminder_time):
                    continue

                tenant_res = await db.execute(
                    select(Tenant).where(Tenant.id == sub.tenant_id)
                )
                tenant = tenant_res.scalar_one_or_none()
                if not tenant:
                    continue

                client = sub.client
                if not client:
                    continue

                service_name = sub.service.name if sub.service else "Servicio"
                client_name = client.full_name or client.local_username or "Cliente"
                streaming_email = sub.streaming_email or ""

                days_until_expiry = (sub.expires_at.date() - today).days

                for warning_day in warning_days:
                    if days_until_expiry != warning_day:
                        continue

                    sent_for_date = today
                    recipients = self._resolve_recipients(
                        recipient_mode, tenant, client
                    )

                    for recipient_type, recipient_phone in recipients:
                        if not recipient_phone:
                            continue

                        log = SubscriptionReminderLog(
                            tenant_id=sub.tenant_id,
                            subscription_id=sub.id,
                            recipient_type=recipient_type,
                            recipient_phone=recipient_phone,
                            days_before_expiry=warning_day,
                            sent_for_date=sent_for_date,
                            status="pending",
                        )
                        db.add(log)
                        try:
                            await db.flush()
                        except Exception:
                            await db.rollback()
                            await restore_rls_context(db)
                            continue

                        locale = getattr(tenant, "locale", "en") or "en"
                        message = self._render_reminder_message(
                            service_name=service_name,
                            client_name=client_name,
                            days=warning_day,
                            streaming_email=streaming_email,
                            locale=locale,
                        )

                        items.append(
                            {
                                "id": str(log.id),
                                "subscription_id": str(sub.id),
                                "tenant_id": str(sub.tenant_id),
                                "recipient_type": recipient_type,
                                "recipient_phone": recipient_phone,
                                "message": message,
                                "evolution_instance_name": tenant.evolution_instance_name
                                or "",
                                "days_before_expiry": warning_day,
                            }
                        )
            except Exception:
                continue

        if items:
            await db.commit()
            await restore_rls_context(db)

        next_cursor: str | None = None
        if has_more and subs:
            next_cursor = subs[-1].expires_at.isoformat()

        return {"items": items, "next_cursor": next_cursor}

    def _is_reminder_time_ok(self, now: datetime, reminder_time: str) -> bool:
        """Check if current time is at or after configured reminder time.

        For v1 all times are treated as UTC.
        """
        try:
            hour, minute = reminder_time.split(":")
            reminder = now.replace(
                hour=int(hour), minute=int(minute), second=0, microsecond=0
            )
            return now >= reminder
        except (ValueError, AttributeError):
            return True

    def _resolve_recipients(
        self, mode: str, tenant: Any, client: Any
    ) -> list[tuple[str, str | None]]:
        recipients: list[tuple[str, str | None]] = []
        tenant_phone = getattr(tenant, "whatsapp_phone", None)
        client_phone = getattr(client, "phone", None)

        if mode in ("tenant_only",):
            recipients.append(("tenant", tenant_phone))
        elif mode in ("client_only",):
            recipients.append(("client", client_phone))
        else:
            recipients.append(("tenant", tenant_phone))
            recipients.append(("client", client_phone))
        return recipients

    @staticmethod
    def _render_reminder_message(
        service_name: str, client_name: str, days: int, streaming_email: str, locale: str = "es"
    ) -> str:
        day_word_key = "reminder.day" if days == 1 else "reminder.days"
        day_word = i18n_t(locale, day_word_key)
        return i18n_t(
            locale,
            "reminder.subscription.expiring",
            service_name=service_name,
            client_name=client_name,
            days=str(days),
            day_word=day_word,
            streaming_email=streaming_email,
        )

    # ------------------------------------------------------------------
    # Reminder log status updates
    # ------------------------------------------------------------------

    async def mark_reminder_sent(
        self, db: AsyncSession, log_id: uuid.UUID
    ) -> dict[str, Any] | None:
        res = await db.execute(
            select(SubscriptionReminderLog).where(SubscriptionReminderLog.id == log_id)
        )
        log = res.scalar_one_or_none()
        if not log:
            return None

        now = datetime.now(timezone.utc)
        log.status = "sent"
        log.sent_at = now
        log.last_error = None
        await db.commit()
        await restore_rls_context(db)

        return {
            "id": str(log.id),
            "status": log.status,
            "sent_at": log.sent_at.isoformat() if log.sent_at else None,
        }

    async def mark_reminder_failed(
        self, db: AsyncSession, log_id: uuid.UUID, reason: str | None = None
    ) -> dict[str, Any] | None:
        res = await db.execute(
            select(SubscriptionReminderLog).where(SubscriptionReminderLog.id == log_id)
        )
        log = res.scalar_one_or_none()
        if not log:
            return None

        log.attempt_count = (log.attempt_count or 0) + 1
        log.last_error = reason or "Unknown error"

        if log.attempt_count >= 3:
            log.status = "failed"

        await db.commit()
        await restore_rls_context(db)

        return {
            "id": str(log.id),
            "status": log.status,
            "attempt_count": log.attempt_count,
            "last_error": log.last_error,
        }

    async def run_reminders_stub(self) -> list[dict[str, Any]]:
        """Placeholder for reminders in the job endpoint.

        Actual reminders are generated via ``generate_reminder_payloads``.
        """
        return []
