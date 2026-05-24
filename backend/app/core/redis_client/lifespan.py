"""Module-level Redis lifecycle helpers (init, close, accessors)."""

from __future__ import annotations

from typing import Any, Optional

from app.core.config import settings

from .manager import RedisConnectionManager

_manager: RedisConnectionManager | None = None


async def init_redis() -> None:
    """Initialise the Redis connection manager.

    Reads settings from ``app.core.config.settings``.

    * If ``redis_primary_url`` is set, it becomes the primary URL.
    * Otherwise falls back to the legacy ``redis_url`` for backward
      compatibility.
    """
    global _manager

    primary_url = settings.redis_primary_url or settings.redis_url or ""
    backup_url = settings.redis_backup_url or ""

    if not primary_url and not backup_url:
        _manager = None
        return

    _manager = RedisConnectionManager(
        primary_url=primary_url,
        backup_url=backup_url,
        pool_size=settings.redis_pool_size,
        socket_timeout=settings.redis_socket_timeout_seconds,
        connect_timeout=settings.redis_connect_timeout_seconds,
        health_check_interval=settings.redis_health_check_interval_seconds,
        failure_threshold=settings.redis_failover_failure_threshold,
        open_window_seconds=settings.redis_breaker_open_seconds,
    )


async def close_redis() -> None:
    """Close the Redis connection manager and all its clients."""
    global _manager
    if _manager is not None:
        await _manager.close()
        _manager = None


async def get_redis() -> Optional[Any]:
    """Return the active Redis client, or ``None`` if unavailable.

    Services should check for ``None`` and handle Redis unavailability
    gracefully.
    """
    if _manager is None:
        return None
    return _manager.get_active_client()


def get_redis_manager() -> RedisConnectionManager | None:
    """Return the Redis connection manager (or ``None`` if unconfigured).

    The manager provides the :meth:`RedisConnectionManager.execute`
    method that session services use for failover-aware Redis operations.
    """
    return _manager
