"""Ephemeral in-memory result cache for lookup job values.

``result_value`` must not be persisted in the database (design decision).
This module provides a lightweight dict-based cache with TTL expiry.

For production at scale, swap this for a Redis-backed implementation
without changing the worker or endpoint code.
"""

from __future__ import annotations

import time
from uuid import UUID
from typing import TypedDict

_ENTRY_TTL_SECONDS = 60


class _CacheEntry(TypedDict):
    result_type: str
    result_value: str
    expires_at: float


_cache: dict[str, _CacheEntry] = {}


def store_result(
    job_id: UUID,
    result_type: str,
    result_value: str,
    ttl_seconds: int = _ENTRY_TTL_SECONDS,
) -> None:
    """Store an ephemeral result for a completed lookup job.

    ``result_value`` is the extracted code or URL string.  TTL defaults
    to 60 seconds — plenty for the n8n polling window.
    """
    _cache[str(job_id)] = {
        "result_type": result_type,
        "result_value": result_value,
        "expires_at": time.monotonic() + ttl_seconds,
    }


def get_result(job_id: UUID) -> tuple[str, str] | None:
    """Retrieve an ephemeral result, or ``None`` if expired/missing.

    Returns ``(result_type, result_value)`` when found and fresh.
    Cleans up expired entries lazily on read.
    """
    key = str(job_id)
    entry = _cache.get(key)
    if entry is None:
        return None
    if time.monotonic() > entry["expires_at"]:
        _cache.pop(key, None)
        return None
    return (entry["result_type"], entry["result_value"])


def clear_result(job_id: UUID) -> None:
    """Remove a cached result (e.g. after n8n consumed it)."""
    _cache.pop(str(job_id), None)


def purge_expired() -> int:
    """Remove all expired cache entries. Returns count purged."""
    now = time.monotonic()
    expired: list[str] = [k for k, v in _cache.items() if v["expires_at"] < now]
    for key in expired:
        _cache.pop(key, None)
    return len(expired)


__all__ = ["store_result", "get_result", "clear_result", "purge_expired"]
