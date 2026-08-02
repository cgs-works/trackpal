"""Netflix URL resolution and optional diagnostics."""

from .r2_diagnostics import (
    DiagnosticStorage,
    DisabledDiagnosticStorage,
    R2Diagnostics,
    upload_netflix_diagnostic,
)
from .resolver import (
    NetflixResolver,
    NetflixResolverPort,
    extract_netflix_verify_code,
    fetch_netflix_code_from_url,
)

__all__ = [
    "DiagnosticStorage",
    "DisabledDiagnosticStorage",
    "NetflixResolver",
    "NetflixResolverPort",
    "R2Diagnostics",
    "extract_netflix_verify_code",
    "fetch_netflix_code_from_url",
    "upload_netflix_diagnostic",
]
