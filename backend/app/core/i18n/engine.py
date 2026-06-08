"""In-memory i18n engine with named-placeholder templates and en-fallback.

Catalogs live in sibling modules and are merged at startup in ``__init__``.
This module holds the lookup/formatting logic.
"""

from __future__ import annotations

import logging
from collections import Counter
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Counter for missing-key events (per-process; not shared across workers)
# ---------------------------------------------------------------------------
missing_key_counter: Counter[str] = Counter()


def _warn_missing(key: str, locale: str) -> None:
    missing_key_counter[key] += 1
    count = missing_key_counter[key]
    # Log every 1st, 10th, 100th… occurrence to avoid spam
    if count in (1, 10, 100, 1000) or count % 10000 == 0:
        logger.warning(
            "i18n missing key %r in locale %r (count=%d)", key, locale, count
        )


def t(locale: str, key: str, /, **params: Any) -> str:
    """Translate *key* in *locale*, falling back to English.

    Parameters
    ----------
    locale : str
        Target locale code (``"en"``, ``"es"``).
    key : str
        Dot-separated translation key.
    **params
        Named placeholders injected via ``str.format``.

    Returns
    -------
    str
        Translated and formatted string, or the key itself if both locale
        and English are missing (defensive fallback).

    Notes
    -----
    Missing keys emit a ``logger.warning`` and increment
    ``missing_key_counter``.  The counter is per-process — not shared
    across workers — and is intended for dev/QA awareness.
    """
    # Late import to avoid circular dependency — ``__init__`` sets these
    # on the module before importing ``t``.
    from app.core.i18n import _MERGED, _CATALOG_EN, _CATALOGS

    # Try requested locale — merged catalog includes en fallback keys
    merged = _MERGED.get(locale)
    if merged is not None:
        template = merged.get(key)
        if template is not None:
            # Warn if key missing from raw locale (found via English fallback)
            if locale != "en":
                raw = _CATALOGS.get(locale, {})
                if key not in raw:
                    _warn_missing(key, locale)
            return template.format(**params)

    # Fallback: try English directly
    en = _MERGED.get("en", _CATALOG_EN)
    template = en.get(key)
    if template is not None:
        if locale != "en":
            _warn_missing(key, locale)
        return template.format(**params)

    # Defensive: key not found at all
    _warn_missing(key, locale)
    return key


def get_merged_catalog(locale: str) -> dict[str, str]:
    """Return the precomputed merged catalog for *locale* (including en fallback keys).

    The returned dict is a copy to prevent accidental mutation.
    """
    from app.core.i18n import _MERGED, _CATALOG_EN

    merged = _MERGED.get(locale)
    if merged is not None:
        return dict(merged)
    # Fallback to English for unknown locales
    return dict(_MERGED.get("en", _CATALOG_EN))
