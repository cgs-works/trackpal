"""Optional diagnostics storage for failed Netflix HTML extraction."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Protocol

logger = logging.getLogger(__name__)


class DiagnosticStorage(Protocol):
    """Minimal storage port used by diagnostic uploads."""

    def put(self, key: str, body: bytes, content_type: str) -> str | None:
        """Store an object and return its identifier or URL."""


class DisabledDiagnosticStorage:
    """No-op storage used when diagnostics are not configured."""

    def put(self, key: str, body: bytes, content_type: str) -> str | None:
        return None


class R2Diagnostics:
    """Best-effort uploader that never changes the lookup result."""

    def __init__(self, storage: DiagnosticStorage | None = None) -> None:
        self._storage = storage or DisabledDiagnosticStorage()

    def upload(self, html_content: str, nftoken_prefix: str = "") -> str | None:
        """Upload HTML with a bounded, token-safe object key."""
        safe_prefix = "".join(char for char in nftoken_prefix if char.isalnum())[:12]
        timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S")
        key = f"debug/netflix/verify_{timestamp}_{safe_prefix}.html"
        try:
            return self._storage.put(
                key,
                html_content.encode("utf-8"),
                "text/html; charset=utf-8",
            )
        except Exception:  # noqa: BLE001 - diagnostics are best effort
            logger.warning("Failed to upload Netflix diagnostic HTML")
            return None


def upload_netflix_diagnostic(
    html_content: str,
    nftoken_prefix: str = "",
    *,
    diagnostics: R2Diagnostics | None = None,
) -> str | None:
    """Compatibility helper for best-effort diagnostic upload."""
    return (diagnostics or R2Diagnostics()).upload(html_content, nftoken_prefix)


__all__ = [
    "DiagnosticStorage",
    "DisabledDiagnosticStorage",
    "R2Diagnostics",
    "upload_netflix_diagnostic",
]
