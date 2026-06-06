"""Subscription cancel/reactivate/renew lifecycle handlers."""

from __future__ import annotations
from datetime import datetime, timezone
from zoneinfo import ZoneInfo


async def _handle_subscriptions_cancel_confirm(
    self, phone, msg, session, session_service, tenant_id, db
) -> str:
    if msg.strip().lower() not in ("confirmar", "confirm"):
        return self._t(self.KEY_SUBSCRIPTIONS_CONFIRM_REPROMPT)
    subscription_id = self._safe_uuid(session.selected_tenant_id)
    if (
        subscription_id is None
        or tenant_id is None
        or db is None
        or self._subscription_service is None
    ):
        return self._t("wa.tenant.errors.subscription_cancel_failed")
    cancelled = await self._subscription_service.cancel_subscription(
        db, tenant_id, subscription_id
    )
    if cancelled is None:
        return self._t(self.KEY_SUBSCRIPTIONS_INVALID_SELECTION)
    if session_service is not None:
        await session_service.clear_session(f"admin:{phone}")
    return self._with_main_menu(self._t(self.KEY_SUBSCRIPTIONS_CANCEL_SUCCESS))


async def _handle_subscriptions_reactivate_duration(
    self, phone, msg, session, session_service, tenant_id, db
) -> str:
    # Get tenant timezone before deleting references
    _tz = timezone.utc
    if tenant_id is not None and db is not None and self._subscription_service is not None:
        try:
            _settings = await self._subscription_service.get_reminder_settings(
                db, tenant_id
            )
            _tz = ZoneInfo(_settings.timezone)
        except Exception:
            pass
    del phone, tenant_id, db
    duration_type = self.SUBSCRIPTIONS_DURATION_MAP.get(msg)
    if duration_type is None:
        return self._t(self.KEY_SUBSCRIPTIONS_INVALID_SELECTION)
    session.temp_data = {
        "duration_type": duration_type,
        "starts_at": datetime.now(_tz).isoformat(),
    }
    if duration_type == "custom":
        session.step = self.SUBSCRIPTIONS_STEP_REACTIVATE_CUSTOM_DATE
        if session_service is not None:
            await session_service.save_session(session)
        return self._t(self.KEY_SUBSCRIPTIONS_REACTIVATE_CUSTOM_DATE_PROMPT)
    session.step = self.SUBSCRIPTIONS_STEP_REACTIVATE_CONFIRM
    if session_service is not None:
        await session_service.save_session(session)
    return self._build_subscription_reactivate_confirm(session.temp_data)


async def _handle_subscriptions_reactivate_custom_date(
    self, phone, msg, session, session_service, tenant_id, db
) -> str:
    del phone, tenant_id, db
    expires_at = self._parse_iso_date(msg)
    if expires_at is None:
        return self._t("wa.tenant.errors.invalid_date")
    session.temp_data["expires_at"] = expires_at.isoformat()
    session.step = self.SUBSCRIPTIONS_STEP_REACTIVATE_CONFIRM
    if session_service is not None:
        await session_service.save_session(session)
    return self._build_subscription_reactivate_confirm(session.temp_data)


async def _handle_subscriptions_reactivate_confirm(
    self, phone, msg, session, session_service, tenant_id, db
) -> str:
    if msg.strip().lower() not in ("confirmar", "confirm"):
        return self._t(self.KEY_SUBSCRIPTIONS_CONFIRM_REPROMPT)
    subscription_id = self._safe_uuid(session.selected_tenant_id)
    if (
        subscription_id is None
        or tenant_id is None
        or db is None
        or self._subscription_service is None
    ):
        return self._t("wa.tenant.errors.subscription_reactivate_failed")
    duration_type = session.temp_data["duration_type"]
    starts_at = datetime.fromisoformat(session.temp_data["starts_at"])
    expires_at_raw = session.temp_data.get("expires_at")
    expires_at = datetime.fromisoformat(expires_at_raw) if expires_at_raw else None
    reactivated = await self._subscription_service.reactivate_subscription(
        db,
        tenant_id,
        subscription_id,
        duration_type,
        starts_at=starts_at,
        expires_at=expires_at,
    )
    if reactivated is None:
        return self._t(self.KEY_SUBSCRIPTIONS_INVALID_SELECTION)
    if session_service is not None:
        await session_service.clear_session(f"admin:{phone}")
    return self._with_main_menu(self._t(self.KEY_SUBSCRIPTIONS_REACTIVATE_SUCCESS))


async def _handle_subscriptions_renew_duration(
    self, phone, msg, session, session_service, tenant_id, db
) -> str:
    del phone
    duration_type = self.SUBSCRIPTIONS_DURATION_MAP.get(msg)
    if duration_type is None:
        return self._t(self.KEY_SUBSCRIPTIONS_INVALID_SELECTION)
    session.temp_data = {"duration_type": duration_type}
    if duration_type == "custom":
        session.step = self.SUBSCRIPTIONS_STEP_RENEW_CUSTOM_DATE
        if session_service is not None:
            await session_service.save_session(session)
        return self._t(self.KEY_SUBSCRIPTIONS_RENEW_CUSTOM_DATE_PROMPT)
    session.step = self.SUBSCRIPTIONS_STEP_RENEW_CONFIRM
    if session_service is not None:
        await session_service.save_session(session)
    return await self._build_subscription_renew_confirm(session, tenant_id, db)


async def _handle_subscriptions_renew_custom_date(
    self, phone, msg, session, session_service, tenant_id, db
) -> str:
    del phone
    expires_at = self._parse_iso_date(msg)
    if expires_at is None:
        return self._t("wa.tenant.errors.invalid_date")
    session.temp_data["expires_at"] = expires_at.isoformat()
    session.step = self.SUBSCRIPTIONS_STEP_RENEW_CONFIRM
    if session_service is not None:
        await session_service.save_session(session)
    return await self._build_subscription_renew_confirm(session, tenant_id, db)


async def _handle_subscriptions_renew_confirm(
    self, phone, msg, session, session_service, tenant_id, db
) -> str:
    if msg.strip().lower() not in ("confirmar", "confirm"):
        return self._t(self.KEY_SUBSCRIPTIONS_CONFIRM_REPROMPT)
    subscription_id = self._safe_uuid(session.selected_tenant_id)
    if (
        subscription_id is None
        or tenant_id is None
        or db is None
        or self._subscription_service is None
    ):
        return self._t("wa.tenant.errors.subscription_renew_failed")
    duration_type = session.temp_data["duration_type"]
    expires_at_raw = session.temp_data.get("expires_at")
    expires_at = datetime.fromisoformat(expires_at_raw) if expires_at_raw else None
    renewed = await self._subscription_service.renew_subscription(
        db,
        tenant_id,
        subscription_id,
        duration_type,
        expires_at=expires_at,
    )
    if renewed is None:
        return self._t(self.KEY_SUBSCRIPTIONS_INVALID_SELECTION)
    if session_service is not None:
        await session_service.clear_session(f"admin:{phone}")
    return self._with_main_menu(self._t(self.KEY_SUBSCRIPTIONS_RENEW_SUCCESS))
