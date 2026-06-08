"""Subscription confirm-build helpers for the Tenant Console."""

from __future__ import annotations

from datetime import datetime, timezone


def _build_subscription_create_confirm(self, data: dict) -> str:
    starts_at = datetime.fromisoformat(data["starts_at"])
    expires_at_raw = data.get("expires_at")
    expires_at = (
        datetime.fromisoformat(expires_at_raw)
        if expires_at_raw
        else self._calculate_subscription_expiry(starts_at, data["duration_type"])
    )
    return self._t(
        self.KEY_SUBSCRIPTIONS_CREATE_CONFIRM_TEMPLATE,
        client_name=data.get("client_name", "—"),
        service_name=data.get("service_name", "—"),
        plan_name=data.get("plan_name", "—"),
        email=data.get("streaming_email", "—"),
        password=data.get("streaming_password") or "—",
        profile_name=data.get("profile_name") or "—",
        pin=data.get("profile_pin") or "—",
        duration_label=self._format_subscription_duration(data["duration_type"]),
        starts_at=self._format_short_date(starts_at),
        expires_at=self._format_short_date(expires_at),
    )


def _build_subscription_reactivate_confirm(self, data: dict) -> str:
    starts_at = datetime.fromisoformat(data["starts_at"])
    expires_at_raw = data.get("expires_at")
    expires_at = (
        datetime.fromisoformat(expires_at_raw)
        if expires_at_raw
        else self._calculate_subscription_expiry(starts_at, data["duration_type"])
    )
    return self._t(
        self.KEY_SUBSCRIPTIONS_REACTIVATE_CONFIRM_TEMPLATE,
        duration_label=self._format_subscription_duration(data["duration_type"]),
        starts_at=self._format_short_date(starts_at),
        expires_at=self._format_short_date(expires_at),
    )


async def _build_subscription_renew_confirm(self, session, tenant_id, db):
    subscription = await self._get_selected_subscription(session, tenant_id, db)
    if subscription is None:
        return self._t(self.KEY_SUBSCRIPTIONS_INVALID_SELECTION)
    duration_type = session.temp_data["duration_type"]
    expires_at_raw = session.temp_data.get("expires_at")
    base_expires = subscription.expires_at
    if base_expires.tzinfo is None:
        base_expires = base_expires.replace(tzinfo=timezone.utc)
    expires_at = (
        datetime.fromisoformat(expires_at_raw)
        if expires_at_raw
        else self._calculate_subscription_expiry(base_expires, duration_type)
    )
    return self._t(
        self.KEY_SUBSCRIPTIONS_RENEW_CONFIRM_TEMPLATE,
        duration_label=self._format_subscription_duration(duration_type),
        expires_at=self._format_short_date(expires_at),
    )
