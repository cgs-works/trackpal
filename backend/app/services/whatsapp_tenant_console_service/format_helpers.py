"""Formatting utility functions for the Tenant Console."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
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


def format_price(amount: Decimal | None, symbol: str | None, locale: str) -> str:
    """Format a plan price for WhatsApp text; None → 'on request'."""
    from app.core.i18n import t as _i18n_t

    if amount is None:
        return _i18n_t(locale, "wa.tenant.catalog.price_on_request")
    if not symbol:
        return f"{amount:.2f}"
    # Spanish locale: comma as decimal separator (e.g. "Bs. 12,50")
    if locale == "es":
        formatted = f"{amount:.2f}".replace(".", ",", 1)
        return f"{symbol} {formatted}"
    return f"{symbol} {amount:.2f}"


def _parse_price_input(value: str) -> Decimal | None:
    """Parse '12.50' or '12,50' → Decimal; None on invalid."""
    text = value.strip().replace(",", ".")
    try:
        parsed = Decimal(text)
    except InvalidOperation:
        return None
    if parsed < 0 or parsed != parsed.quantize(Decimal("0.01")):
        return None
    return parsed


# Price skip words (used by catalog flow)
PRICE_SKIP_WORDS = {"sin precio", "none", "omitir", "skip"}
