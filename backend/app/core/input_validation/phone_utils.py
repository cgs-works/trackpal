"""Phone string utility functions (JID suffix stripping)."""

from __future__ import annotations


def _strip_phone_suffixes(raw: str) -> str:
    """Strip WhatsApp JID suffix and device suffix from a phone string.

    Handles:

    * WhatsApp JID suffixes (``@c.us``, ``@s.whatsapp.net``)
    * Device suffixes after ``:``

    Args:
        raw: Raw phone string potentially containing suffixes.

    Returns:
        Clean phone string with suffixes removed.
    """
    if "@" in raw:
        raw = raw.split("@", 1)[0]
    if ":" in raw:
        raw = raw.split(":", 1)[0]
    return raw
