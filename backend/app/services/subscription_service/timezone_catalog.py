"""Timezone validation and catalog with external-provider fallback.

Provides IANA timezone validation and a list_timezones service that
sources timezone data using a three-tier strategy:

1. External provider if configured/available.
2. Cached backend copy from system zoneinfo if available.
3. Bundled local fallback data.
"""

import logging
from zoneinfo import ZoneInfo, available_timezones

from app.services.subscription_service.timezone_catalog_fallback import (
    get_fallback_timezones,
)

logger = logging.getLogger(__name__)

_VALID_TIMEZONES: frozenset[str] | None = None


def _get_valid_timezones() -> frozenset[str]:
    """Return all IANA timezone identifiers known to zoneinfo."""
    global _VALID_TIMEZONES
    if _VALID_TIMEZONES is None:
        _VALID_TIMEZONES = frozenset(available_timezones())
    return _VALID_TIMEZONES


def validate_timezone(tz_str: str | None) -> bool:
    """Return True if tz_str is a valid IANA timezone identifier.

    Accepts None (meaning not provided) as valid so callers can
    distinguish between "not set" and "invalid value".
    """
    if tz_str is None:
        return True
    if not tz_str.strip():
        return False
    valid = _get_valid_timezones()
    return tz_str in valid


def compute_utc_offset(tz_str: str) -> str:
    """Compute a human-readable UTC offset string for a timezone.

    Returns something like 'UTC+01:00' or 'UTC-05:00'.
    Falls back to empty string on error.
    """
    try:
        tz = ZoneInfo(tz_str)
        import datetime

        now = datetime.datetime.now(datetime.timezone.utc)
        offset = tz.utcoffset(now)
        if offset is None:
            return ""
        total_seconds = int(offset.total_seconds())
        sign = "+" if total_seconds >= 0 else "-"
        hours = abs(total_seconds) // 3600
        minutes = (abs(total_seconds) % 3600) // 60
        # noqa
        return f"UTC{sign}{hours:02d}:{minutes:02d}"
    except (KeyError, TypeError, ValueError):
        return ""


def _make_entry(tz_str: str) -> dict[str, str]:
    """Build a timezone entry with value and dynamically computed label."""
    offset = compute_utc_offset(tz_str)
    label = f"{tz_str} ({offset})" if offset else tz_str
    return {"value": tz_str, "label": label}


async def _fetch_external_provider() -> list[dict[str, str]] | None:
    """Attempt to fetch timezone list from an external provider.

    Currently a stub -- returns None to trigger fallback.
    Override via monkeypatch in tests.
    """
    return None


def _normalize_provider_results(
    raw: list[dict[str, str]],
) -> list[dict[str, str]]:
    """Filter and normalize provider results to only valid IANA identifiers."""
    valid = _get_valid_timezones()
    result: list[dict[str, str]] = []
    for entry in raw:
        value = entry.get("value", "")
        if value in valid:
            result.append(_make_entry(value))
    return result


def _load_backend_timezones() -> list[dict[str, str]] | None:
    """Generate timezone list from system zoneinfo data.

    Returns None when zoneinfo has no data (e.g. on systems without
    the ``tzdata`` package), so callers can fall through to the
    bundled fallback.
    """
    tzs = _get_valid_timezones()
    if not tzs:
        return None
    result: list[dict[str, str]] = []
    for tz_str in sorted(tzs):
        result.append(_make_entry(tz_str))
    return result


async def list_timezones() -> list[dict[str, str]]:
    """Return a list of timezone dicts with ``value`` and ``label`` keys.

    Sourcing order:

    1. Try external provider if configured/available.
    2. Otherwise use cached backend copy (system zoneinfo) if available.
    3. Otherwise return bundled local fallback data.
    """
    try:
        raw = await _fetch_external_provider()
        if raw is not None and len(raw) > 0:
            normalized = _normalize_provider_results(raw)
            if normalized:
                return normalized
    except Exception as exc:
        logger.warning("External timezone provider failed: %s", exc)

    cached = _load_backend_timezones()
    if cached is not None and len(cached) > 0:
        return cached

    return get_fallback_timezones()
