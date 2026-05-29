"""Subscription create-flow duration/confirm handlers."""

from __future__ import annotations

from uuid import UUID
from datetime import datetime

from app.core.errors import UserFacingError, translate_error

from . import _context as ctx


async def _handle_subscriptions_create_duration(
    self, phone, msg, session, session_service, tenant_id, db
):
    del phone, tenant_id, db
    duration_type = self.SUBSCRIPTIONS_DURATION_MAP.get(msg)
    if duration_type is None:
        return self._t(self.KEY_SUBSCRIPTIONS_INVALID_SELECTION)

    session.temp_data["duration_type"] = duration_type
    if duration_type == "custom":
        session.step = self.SUBSCRIPTIONS_STEP_CREATE_CUSTOM_DATE
        if session_service is not None:
            await session_service.save_session(session)
        return self._t(self.KEY_SUBSCRIPTIONS_CUSTOM_DATE_PROMPT)

    session.temp_data["expires_at"] = None
    session.step = self.SUBSCRIPTIONS_STEP_CREATE_CONFIRM
    if session_service is not None:
        await session_service.save_session(session)
    return self._build_subscription_create_confirm(session.temp_data)


async def _handle_subscriptions_create_custom_date(
    self, phone, msg, session, session_service, tenant_id, db
):
    del phone, tenant_id, db
    expires_at = self._parse_iso_date(msg)
    if expires_at is None:
        return self._t("wa.tenant.errors.invalid_date")
    session.temp_data["expires_at"] = expires_at.isoformat()
    session.step = self.SUBSCRIPTIONS_STEP_CREATE_CONFIRM
    if session_service is not None:
        await session_service.save_session(session)
    return self._build_subscription_create_confirm(session.temp_data)


async def _handle_subscriptions_create_confirm(
    self, phone, msg, session, session_service, tenant_id, db
):
    if msg.strip().lower() not in ("confirmar", "confirm"):
        return self._t(self.KEY_SUBSCRIPTIONS_CONFIRM_REPROMPT)
    if tenant_id is None or db is None or self._subscription_service is None:
        return self._t("wa.tenant.errors.subscription_create_failed")

    from app.schemas.subscription import SubscriptionCreate

    data = session.temp_data
    starts_at = datetime.fromisoformat(data["starts_at"])
    expires_at_raw = data.get("expires_at")
    expires_at = datetime.fromisoformat(expires_at_raw) if expires_at_raw else None
    payload = SubscriptionCreate(
        client_id=UUID(data["client_id"]),
        service_id=UUID(data["service_id"]),
        plan_id=UUID(data["plan_id"]),
        streaming_email=data["streaming_email"],
        streaming_password=data.get("streaming_password"),
        profile_name=data.get("profile_name"),
        profile_pin=data.get("profile_pin"),
        duration_type=data["duration_type"],
        starts_at=starts_at,
        expires_at=expires_at,
    )
    try:
        await self._subscription_service.create_subscription(db, tenant_id, payload)
    except UserFacingError as exc:
        return "❌ " + translate_error(ctx.get_locale(), exc)
    except ValueError as exc:
        return "❌ " + str(exc)

    if session_service is not None:
        await session_service.clear_session(f"admin:{phone}")
    return (
        self._with_main_menu(self._t(self.KEY_SUBSCRIPTIONS_CREATE_SUCCESS))
        + self._post_action_prompt()
    )
