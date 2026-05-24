"""Reminder payload generation for subscription expiry notifications.

Debt: 213 LoC (target <=200, max 240). Refactor generate_reminder_payloads loop.
"""

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import restore_rls_context
from app.core.i18n import t as i18n_t
from app.models.subscription import (
    Subscription,
    SubscriptionReminderLog,
    SubscriptionReminderSettings,
)
from app.models.tenant import Tenant


def _is_reminder_time_ok(now: datetime, reminder_time: str) -> bool:
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
    mode: str, tenant: Any, client: Any
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


def _render_reminder_message(
    service_name: str,
    client_name: str,
    days: int,
    streaming_email: str,
    locale: str = "es",
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


async def generate_reminder_payloads(
    db: AsyncSession, cursor: str | None = None, page_size: int = 100
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

            if not _is_reminder_time_ok(now, reminder_time):
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
                recipients = _resolve_recipients(recipient_mode, tenant, client)

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
                    message = _render_reminder_message(
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
