"""Catalog V1 — combined service entries."""

from app.services.mail_code_extractor._types import ServiceEntry

from .netflix import SERVICE as NETFLIX_ENTRY
from .disney import SERVICE as DISNEY_ENTRY
from .hbo_max import SERVICE as HBO_MAX_ENTRY
from .spotify import SERVICE as SPOTIFY_ENTRY
from .universal_plus import SERVICE as UNIVERSAL_PLUS_ENTRY
from .prime_video import SERVICE as PRIME_VIDEO_ENTRY

CATALOG_V1: dict[str, ServiceEntry] = {
    "netflix": NETFLIX_ENTRY,
    "disney": DISNEY_ENTRY,
    "hbo_max": HBO_MAX_ENTRY,
    "spotify": SPOTIFY_ENTRY,
    "universal_plus": UNIVERSAL_PLUS_ENTRY,
    "prime_video": PRIME_VIDEO_ENTRY,
}
