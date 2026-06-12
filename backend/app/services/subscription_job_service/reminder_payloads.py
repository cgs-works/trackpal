"""Reminder payload generation for subscription expiry notifications.

Debt: 224 LoC (target <=200, max 240). Refactor generate_reminder_payloads loop.
"""

import logging
from datetime import datetime, timezone
import uuid
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from zoneinfo import ZoneInfo

from app.core.encryption import decrypt_value
from app.core.database import restore_rls_context
from app.core.i18n import t as i18n_t
from app.models.subscription import (
    Subscription,
    SubscriptionReminderLog,
)
from app.services.subscription_job_service.reminder_schedule import (
    compute_days_until_expiry,
    is_reminder_time_ok,
    is_valid_timezone,
    load_batched_reminder_data,
)


logger = logging.getLogger(__name__)

CURSOR_SEP = "|"


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


def _parse_cursor(
    cursor: str,
) -> tuple[datetime, uuid.UUID] | None:
    """Parse composite cursor ``expires_at_iso|id``.

    Returns ``(cursor_dt, cursor_id)`` or ``None`` when the format is
    unparseable (caller falls back to first page).
    """
    try:
        if CURSOR_SEP in cursor:
            dt_str, id_str = cursor.rsplit(CURSOR_SEP, 1)
            cursor_dt = datetime.fromisoformat(dt_str)
            cursor_id = uuid.UUID(id_str)
        else:
            cursor_dt = datetime.fromisoformat(cursor)
            cursor_id = None
    except (ValueError, TypeError):
        return None

    if cursor_dt.tzinfo is None:
        cursor_dt = cursor_dt.replace(tzinfo=timezone.utc)
    return cursor_dt, cursor_id


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
        .order_by(Subscription.expires_at.asc(), Subscription.id.asc())
    )

    if cursor:
        parsed = _parse_cursor(cursor)
        if parsed is not None:
            cursor_dt, cursor_id = parsed
            if cursor_id is not None:
                stmt = stmt.where(
                    or_(
                        Subscription.expires_at > cursor_dt,
                        (
                            (Subscription.expires_at == cursor_dt)
                            & (Subscription.id > cursor_id)
                        ),
                    )
                )
            else:
                stmt = stmt.where(Subscription.expires_at > cursor_dt)

    res = await db.execute(stmt.limit(page_size + 1))
    subs = list(res.unique().scalars().all())

    has_more = len(subs) > page_size
    if has_more:
        subs = subs[:page_size]

    if not subs:
        return {"items": [], "next_cursor": None}

    # Batch-load settings, tenants, and tenant settings — eliminates N+1 queries
    settings_map, tenants_map, tenant_settings_map = await load_batched_reminder_data(db, subs)

    items: list[dict[str, Any]] = []

    for sub in subs:
        try:
            settings = settings_map.get(sub.tenant_id)
            tenant = tenants_map.get(sub.tenant_id)
            tenant_settings = tenant_settings_map.get(sub.tenant_id)

            # Skip if tenant or settings are missing
            if not tenant or not settings:
                continue

            # Skip entire tenant if reminders are disabled
            if not settings.reminders_enabled:
                continue

            # Timezone from TenantSettings; default to UTC if not set
            tz_name = getattr(tenant_settings, "timezone", None) or "UTC"
            if not is_valid_timezone(tz_name):
                # Skip the invalid-timezone tenant, not the whole batch
                continue

            # Check if it's time to send in the tenant's local timezone
            if not is_reminder_time_ok(now, settings.reminder_time, tz_name):
                continue

            client = sub.client
            if not client:
                continue

            service_name = sub.service.name if sub.service else "Servicio"
            client_name = client.full_name or client.username or "Cliente"
            streaming_email = sub.streaming_email or ""

            # Compute tenant-local days-until-expiry
            days_until_expiry = compute_days_until_expiry(sub.expires_at, tz_name, now)

            # Compute tenant-local today for sent_for_date
            tz = ZoneInfo(tz_name)
            local_today = now.astimezone(tz).date()

            warning_days = settings.warning_days or [7, 3, 1]
            for warning_day in warning_days:
                if days_until_expiry != warning_day:
                    continue

                recipients = _resolve_recipients(
                    settings.recipient_mode, tenant, client
                )

                for recipient_type, recipient_phone in recipients:
                    if not recipient_phone:
                        continue

                    # Render message and decrypt token BEFORE persisting
                    # the log — if render/decrypt/payload fails, no log
                    # is created.
                    locale = getattr(tenant_settings, "locale", None) or "en"
                    message = _render_reminder_message(
                        service_name=service_name,
                        client_name=client_name,
                        days=warning_day,
                        streaming_email=streaming_email,
                        locale=locale,
                    )

                    evolution_token = (
                        decrypt_value(tenant.evolution_instance_token) or ""
                    )

                    # All render/decrypt succeeded — now persist the log.
                    log = SubscriptionReminderLog(
                        tenant_id=sub.tenant_id,
                        subscription_id=sub.id,
                        recipient_type=recipient_type,
                        recipient_phone=recipient_phone,
                        days_before_expiry=warning_day,
                        sent_for_date=local_today,
                        status="pending",
                    )
                    db.add(log)

                    # Use a savepoint so a duplicate (unique constraint
                    # violation) rolls back only this log, not the whole
                    # batch.
                    try:
                        async with db.begin_nested():
                            await db.flush()
                    except IntegrityError:
                        # Expected uniqueness conflict — savepoint is
                        # auto-rolled-back; skip this recipient.
                        continue

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
                            "evolution_instance_token": evolution_token,
                            "days_before_expiry": warning_day,
                        }
                    )
        except Exception:
            # Isolate per-subscription failures so a single problematic
            # subscription doesn't abort the entire batch.
            logger.warning(
                "Unexpected error processing subscription %s for reminders; skipping",
                sub.id,
                exc_info=True,
            )
            continue

    if items:
        await db.commit()
        await restore_rls_context(db)

    next_cursor: str | None = None
    if has_more and subs:
        next_cursor = f"{subs[-1].expires_at.isoformat()}{CURSOR_SEP}{subs[-1].id}"

    return {"items": items, "next_cursor": next_cursor}
