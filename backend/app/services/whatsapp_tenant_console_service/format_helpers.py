"""Formatting utility functions for the Tenant Console."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID


def _safe_uuid(value: str | None) -> UUID | None:
    if value is None:
        return None
    try:
        return UUID(value)
    except (ValueError, AttributeError):
        return None


def _format_subscription_duration(duration_type: str) -> str:
    return {
        "1_month": "1 mes",
        "3_months": "3 meses",
        "6_months": "6 meses",
        "9_months": "9 meses",
        "1_year": "1 año",
        "custom": "Personalizada",
    }.get(duration_type, duration_type)


def _format_short_date(value: Any) -> str:
    if value is None:
        return "—"
    if hasattr(value, "strftime"):
        return value.strftime("%Y-%m-%d")
    return str(value)


def _calculate_subscription_expiry(
    starts_at: datetime,
    duration_type: str,
    custom_expires_at: datetime | None = None,
) -> datetime:
    if duration_type == "custom":
        if custom_expires_at is None:
            raise ValueError("custom duration requires expires_at")
        return custom_expires_at
    duration_days = {
        "1_month": 30,
        "3_months": 90,
        "6_months": 180,
        "9_months": 270,
        "1_year": 365,
    }
    return starts_at + timedelta(days=duration_days[duration_type])


def _parse_iso_date(value: str) -> datetime | None:
    try:
        parsed = datetime.strptime(value.strip(), "%Y-%m-%d")
    except ValueError:
        return None
    return parsed.replace(tzinfo=timezone.utc)
