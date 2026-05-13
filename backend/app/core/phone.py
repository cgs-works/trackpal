"""Shared phone normalizer for WhatsApp Master Console.

Ensures every phone value used by the backend is canonical digits-only
text without ``+``, WhatsApp JID suffixes, or device suffixes.

Usage::

    from app.core.phone import normalize_phone

    canonical = normalize_phone("+1234567890@c.us")  # "1234567890"
"""

import re


def normalize_phone(value: str | None) -> str | None:
    """Normalize a phone value to canonical digits-only form.

    Handles:
    - ``+`` prefix removal
    - WhatsApp JID suffixes (``@c.us``, ``@s.whatsapp.net``)
    - Device suffixes after ``:``
    - Spaces, dashes, parentheses, and other non-digit characters
    - Blank, ``None``, or no-digit input → ``None``

    Returns:
        Canonical digits-only string, or ``None`` for blank/empty input.
    """
    if value is None:
        return None

    raw = str(value).strip()

    if not raw:
        return None

    # Strip WhatsApp JID suffix (e.g. @c.us, @s.whatsapp.net)
    if "@" in raw:
        raw = raw.split("@", 1)[0]

    # Strip device suffix after :
    if ":" in raw:
        raw = raw.split(":", 1)[0]

    # Keep only digits
    digits = re.sub(r"\D", "", raw)

    if not digits:
        return None

    return digits
