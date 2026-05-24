"""In-memory i18n engine with named-placeholder templates and en-fallback.

Catalogs are Python dicts defined in code, loaded at import, merged at
startup.  No per-request file I/O.  Missing keys fall back to English,
emit a warning, and increment an in-process counter.
"""

from __future__ import annotations

from typing import Final

from app.core import VALID_LOCALES

from .catalogs_en_general import _CATALOG_EN_GENERAL
from .catalogs_en_frontend import _CATALOG_EN_FRONTEND
from .catalogs_en_wa import _CATALOG_EN_WA
from .catalogs_es_general import _CATALOG_ES_GENERAL
from .catalogs_es_frontend import _CATALOG_ES_FRONTEND
from .catalogs_es_wa import _CATALOG_ES_WA

_CATALOG_EN: Final[dict[str, str]] = {
    **_CATALOG_EN_GENERAL,
    **_CATALOG_EN_WA,
    **_CATALOG_EN_FRONTEND,
}

_CATALOG_ES: Final[dict[str, str]] = {
    **_CATALOG_ES_GENERAL,
    **_CATALOG_ES_WA,
    **_CATALOG_ES_FRONTEND,
}

# ---------------------------------------------------------------------------
# Source catalogs — immutable once loaded
# ---------------------------------------------------------------------------
_CATALOGS: Final[dict[str, dict[str, str]]] = {
    "en": _CATALOG_EN,
    "es": _CATALOG_ES,
}

# ---------------------------------------------------------------------------
# Merged catalogs: precompute en-fallback for each locale at import time.
# _MERGED["en"] == _CATALOG_EN  (fast path, no fallback needed)
# _MERGED["es"] == _CATALOG_ES | _CATALOG_EN  (en keys are fallback)
# ---------------------------------------------------------------------------
_MERGED: dict[str, dict[str, str]] = {}

for loc in VALID_LOCALES:
    base = dict(_CATALOGS.get(loc, {}))
    if loc != "en":
        # Add any keys from en that are missing in the locale catalog
        for k, v in _CATALOG_EN.items():
            base.setdefault(k, v)
    _MERGED[loc] = base

# Ensure English is always available (fallback for unknown locales too)
if "en" not in _MERGED:
    _MERGED["en"] = dict(_CATALOG_EN)

# Convenience aliases
LOCALE_NAMES: Final[dict[str, str]] = {
    "en": "English",
    "es": "Español",
}

# Import engine — its ``t`` / ``get_merged_catalog`` do a late import of
# ``_MERGED`` / ``_CATALOG_EN`` / ``_CATALOGS`` which are already defined
# above, so the circular import resolves correctly.
from .engine import get_merged_catalog, missing_key_counter, t  # noqa: F401, E402

__all__ = [
    "get_merged_catalog",
    "LOCALE_NAMES",
    "missing_key_counter",
    "t",
]
