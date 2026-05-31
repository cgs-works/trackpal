"""Bundled fallback timezone catalog for when external provider is unavailable.

Provides a curated set of common IANA timezones with dynamically computed
UTC offset labels. This file should never depend on network access or
external services.
"""

from zoneinfo import ZoneInfo
import datetime

_FALLBACK_VALUES: list[str] = [
    "Africa/Cairo",
    "Africa/Casablanca",
    "Africa/Johannesburg",
    "Africa/Lagos",
    "America/Argentina/Buenos_Aires",
    "America/Bogota",
    "America/Caracas",
    "America/Chicago",
    "America/Denver",
    "America/Guatemala",
    "America/Halifax",
    "America/Lima",
    "America/Los_Angeles",
    "America/Mexico_City",
    "America/New_York",
    "America/Panama",
    "America/Santiago",
    "America/Sao_Paulo",
    "America/Toronto",
    "America/Vancouver",
    "Asia/Bangkok",
    "Asia/Dubai",
    "Asia/Hong_Kong",
    "Asia/Jakarta",
    "Asia/Kolkata",
    "Asia/Manila",
    "Asia/Seoul",
    "Asia/Shanghai",
    "Asia/Singapore",
    "Asia/Tokyo",
    "Australia/Melbourne",
    "Australia/Sydney",
    "Europe/Berlin",
    "Europe/Helsinki",
    "Europe/Lisbon",
    "Europe/London",
    "Europe/Madrid",
    "Europe/Moscow",
    "Europe/Paris",
    "Europe/Rome",
    "Europe/Stockholm",
    "Europe/Zurich",
    "Pacific/Auckland",
    "Pacific/Honolulu",
    "UTC",
]


def _compute_offset(tz_str: str) -> str:
    """Compute a human-readable UTC offset string for a timezone."""
    try:
        tz = ZoneInfo(tz_str)
        now = datetime.datetime.now(datetime.timezone.utc)
        offset = tz.utcoffset(now)
        if offset is None:
            return ""
        total_seconds = int(offset.total_seconds())
        sign = "+" if total_seconds >= 0 else "-"
        hours = abs(total_seconds) // 3600
        minutes = (abs(total_seconds) % 3600) // 60
        return f"UTC{sign}{hours:02d}:{minutes:02d}"
    except (KeyError, TypeError, ValueError):
        return ""


def get_fallback_timezones() -> list[dict[str, str]]:
    """Return bundled fallback timezone list with dynamically computed labels."""
    result: list[dict[str, str]] = []
    for tz_str in _FALLBACK_VALUES:
        offset = _compute_offset(tz_str)
        label = f"{tz_str} ({offset})" if offset else tz_str
        result.append({"value": tz_str, "label": label})
    return result
