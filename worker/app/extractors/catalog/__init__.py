"""Catalog V1 for supported mail code services."""

from collections.abc import Mapping
from types import MappingProxyType

from app.extractors.types import ServiceEntry

from .disney import SERVICE as DISNEY_ENTRY
from .hbo_max import SERVICE as HBO_MAX_ENTRY
from .netflix import SERVICE as NETFLIX_ENTRY
from .prime_video import SERVICE as PRIME_VIDEO_ENTRY
from .spotify import SERVICE as SPOTIFY_ENTRY
from .universal_plus import SERVICE as UNIVERSAL_PLUS_ENTRY

CATALOG_V1: Mapping[str, ServiceEntry] = MappingProxyType(
    {
        "netflix": NETFLIX_ENTRY,
        "disney": DISNEY_ENTRY,
        "hbo_max": HBO_MAX_ENTRY,
        "spotify": SPOTIFY_ENTRY,
        "universal_plus": UNIVERSAL_PLUS_ENTRY,
        "prime_video": PRIME_VIDEO_ENTRY,
    }
)


def get_service_entry(service_key: str) -> ServiceEntry | None:
    """Look up a service entry by key, or return ``None`` if unknown."""
    return CATALOG_V1.get(service_key)
