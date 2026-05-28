"""Versioned mail code extraction catalog — V1.

Migrated from ``pending-migration/subjects.py``.
"""

from ._types import ServiceEntry
from .catalog import CATALOG_V1 as _DATA

CATALOG_V1: dict[str, ServiceEntry] = _DATA


def get_service_entry(service_key: str) -> ServiceEntry | None:
    """Look up a service entry by its key.

    Returns ``None`` when the service key is unknown.
    """
    return CATALOG_V1.get(service_key)
