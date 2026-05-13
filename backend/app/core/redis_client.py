"""Redis connection manager with active-passive primary/backup pools.

Manages process-lifetime Redis client pools for ephemeral WhatsApp
conversational state. Only one primary and one backup pool per process.
"""

from __future__ import annotations

import enum
import time
from typing import Any, Optional

from app.core.config import settings


class RedisUnavailableError(RuntimeError):
    """Raised when Redis is unavailable after exhausting failover.

    Wraps low-level ``ConnectionError``, ``TimeoutError``,
    ``OSError``, and ``redis.RedisError`` so callers can handle
    Redis infrastructure failures with a single domain exception.
    Configuration errors (e.g. no primary URL) remain plain
    ``RuntimeError``.
    """
    pass


class FailoverState(enum.Enum):
    """Circuit-breaker state for Redis active-passive failover.

    States
    ------
    CLOSED:
        Primary Redis is active. Operations go to primary.
    OPEN:
        Backup Redis is active after consecutive primary failures.
    HALF_OPEN:
        Open window expired; next real operation will probe primary.
    """

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class FailoverPolicy:
    """Encapsulates circuit-breaker rules for primary/backup Redis failover.

    Tracks consecutive primary failures.  When the configured threshold
    is reached the breaker opens and operations are routed to the backup.
    After an open window the next real-traffic operation probes the
    primary in half-open state.

    Parameters
    ----------
    failure_threshold:
        Consecutive primary failures before the breaker opens.
    open_window_seconds:
        Seconds the breaker stays open before transitioning to half-open.
    """

    def __init__(
        self,
        failure_threshold: int = 3,
        open_window_seconds: int = 30,
    ) -> None:
        self._failure_threshold = failure_threshold
        self._open_window_seconds = open_window_seconds
        self._state = FailoverState.CLOSED
        self._consecutive_failures = 0
        self._opened_at: float | None = None

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def state(self) -> FailoverState:
        """Current state, with automatic CLOSED→HALF_OPEN transition.

        When the open window has elapsed the internal state transitions
        to ``HALF_OPEN`` so events and callers see the new state.
        """
        if self._state is FailoverState.OPEN and self._opened_at is not None:
            elapsed = time.monotonic() - self._opened_at
            if elapsed >= self._open_window_seconds:
                self._state = FailoverState.HALF_OPEN
                self._opened_at = None
                return FailoverState.HALF_OPEN
        return self._state

    @property
    def consecutive_failures(self) -> int:
        return self._consecutive_failures

    @property
    def failure_threshold(self) -> int:
        return self._failure_threshold

    @property
    def open_window_seconds(self) -> int:
        return self._open_window_seconds

    # ------------------------------------------------------------------
    # Decision
    # ------------------------------------------------------------------

    def should_use_backup(self) -> bool:
        """``True`` when the active store should be the backup."""
        s = self.state
        return s == FailoverState.OPEN

    # ------------------------------------------------------------------
    # Events
    # ------------------------------------------------------------------

    def record_success(self) -> None:
        """Called when a primary operation succeeds.

        Resets the consecutive-failure counter.
        If in half-open, closes the breaker.
        """
        self._consecutive_failures = 0
        if self._state is FailoverState.HALF_OPEN:
            self._state = FailoverState.CLOSED
            self._opened_at = None

    def record_failure(self) -> None:
        """Called when a primary operation fails.

        Increments the consecutive-failure counter.  If the threshold
        is met (or the breaker is half-open and fails) the breaker
        opens.
        """
        self._consecutive_failures += 1

        if self._state is FailoverState.CLOSED:
            if self._consecutive_failures >= self._failure_threshold:
                self._state = FailoverState.OPEN
                self._opened_at = time.monotonic()
        elif self._state is FailoverState.HALF_OPEN:
            self._state = FailoverState.OPEN
            self._opened_at = time.monotonic()
        # In OPEN state we keep counting failures but stay open

    def reset(self) -> None:
        """Reset to initial closed state (for testing/cleanup)."""
        self._state = FailoverState.CLOSED
        self._consecutive_failures = 0
        self._opened_at = None


class RedisConnectionManager:
    """Active-passive Redis connection manager with circuit-breaker failover.

    Owns exactly one primary and one backup ``Redis`` client (each backed
    by a ``ConnectionPool``) for the process lifetime.

    Operations are routed through :meth:`execute`, which uses a
    :class:`FailoverPolicy` to decide whether to use primary or backup,
    records successes/failures, and falls back to backup when the
    breaker opens.

    Parameters
    ----------
    primary_url:
        Redis URL for the primary store (``redis://`` or ``rediss://``).
        When empty, no primary client is created.
    backup_url:
        Redis URL for the backup store (``redis://`` or ``rediss://``).
        When empty, no backup client is created.
    pool_size:
        ``max_connections`` for each pool.
    socket_timeout:
        ``socket_timeout`` for each client connection (seconds).
    connect_timeout:
        ``socket_connect_timeout`` for each client connection (seconds).
    health_check_interval:
        ``health_check_interval`` for each client (seconds).
    redis_cls:
        Redis client class (default ``redis.asyncio.Redis``).  Use a
        fake class in tests.
    failure_threshold:
        Consecutive primary failures before breaker opens.
    open_window_seconds:
        Seconds breaker stays open before transitioning to half-open.
    """

    def __init__(
        self,
        primary_url: str,
        backup_url: str,
        pool_size: int = 20,
        socket_timeout: float = 5.0,
        connect_timeout: float = 5.0,
        health_check_interval: float = 30.0,
        redis_cls: Any = None,
        failure_threshold: int = 3,
        open_window_seconds: int = 30,
    ) -> None:
        self.primary_url = primary_url
        self.backup_url = backup_url
        self.pool_size = pool_size
        self.socket_timeout = socket_timeout
        self.connect_timeout = connect_timeout
        self.health_check_interval = health_check_interval

        if redis_cls is None:
            from redis.asyncio import Redis as _Redis

            redis_cls = _Redis

        self._redis_cls = redis_cls
        self._initialised = False

        self.primary: Any | None = None
        self.backup: Any | None = None

        self._policy = FailoverPolicy(
            failure_threshold=failure_threshold,
            open_window_seconds=open_window_seconds,
        )

        self._init_pools()

    # ------------------------------------------------------------------
    # Initialisation
    # ------------------------------------------------------------------

    def _init_pools(self) -> None:
        """Create primary and backup clients (pools)."""
        common_kwargs: dict[str, Any] = {
            "max_connections": self.pool_size,
            "decode_responses": True,
            "socket_timeout": self.socket_timeout,
            "socket_connect_timeout": self.connect_timeout,
            "health_check_interval": self.health_check_interval,
        }

        if self.primary_url:
            self.primary = self._redis_cls.from_url(
                self.primary_url,
                **common_kwargs,
            )

        if self.backup_url:
            self.backup = self._redis_cls.from_url(
                self.backup_url,
                **common_kwargs,
            )

        self._initialised = True

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def is_available(self) -> bool:
        """``True`` when at least the primary client is configured."""
        return self.primary is not None

    @property
    def used_backup(self) -> bool:
        """``True`` when the failover policy has opened the breaker.

        When ``True``, the backup Redis store is the active target for
        all operations.  The session service uses this signal to decide
        whether a missing session is a normal first-time case or a
        failover scenario.
        """
        return self._policy.should_use_backup()

    def get_active_client(self) -> Any | None:
        """Return the currently active Redis client.

        Uses the failover policy to determine which store is active.
        """
        if self._policy.should_use_backup():
            return self.backup
        return self.primary

    async def execute(
        self,
        operation_name: str,
        async_callable: Any,
    ) -> Any:
        """Run *async_callable(client)* on the active Redis store.

        The callable receives the active Redis client determined by the
        failover policy.

        *   Primary success is reported to the policy (resets failures).
        *   Primary failure is reported to the policy and, if the breaker
            opens, the operation is retried on backup when available.
        *   Backup failures are surfaced to the caller as-is (both-store
            failure).

        Raises
        ------
        RuntimeError
            When no Redis client is configured.
        RedisUnavailableError
            When the active Redis store raises a connection/timeout/OS
            or generic Redis error.
        """
        state = self._policy.state

        try:
            if state is FailoverState.CLOSED:
                return await self._execute_primary(operation_name, async_callable)

            if state is FailoverState.OPEN:
                return await self._execute_backup(operation_name, async_callable)

            # state is HALF_OPEN — try primary, probe recovery
            return await self._execute_half_open(operation_name, async_callable)
        except RuntimeError:
            raise  # configuration errors propagate as-is
        except Exception as exc:
            raise RedisUnavailableError(str(exc)) from exc

    async def _execute_primary(
        self,
        operation_name: str,
        async_callable: Any,
    ) -> Any:
        """Try primary; on failure record it and possibly fall back."""
        if self.primary is None:
            raise RuntimeError("No active Redis client (primary not configured)")

        try:
            result = await async_callable(self.primary)
            self._policy.record_success()
            return result
        except Exception as exc:
            self._policy.record_failure()
            # If breaker just opened and backup exists, retry there
            if self._policy.state is FailoverState.OPEN and self.backup is not None:
                return await async_callable(self.backup)
            raise

    async def _execute_backup(
        self,
        operation_name: str,
        async_callable: Any,
    ) -> Any:
        """Run the operation against backup.  Failures surface as-is."""
        if self.backup is None:
            raise RuntimeError("No active Redis client (backup not configured)")

        return await async_callable(self.backup)

    async def _execute_half_open(
        self,
        operation_name: str,
        async_callable: Any,
    ) -> Any:
        """Probe primary in half-open state."""
        if self.primary is None:
            raise RuntimeError("No active Redis client (primary not configured)")

        try:
            result = await async_callable(self.primary)
            self._policy.record_success()  # closes breaker
            return result
        except Exception as exc:
            self._policy.record_failure()  # re-opens breaker
            # Fall back to backup if available
            if self.backup is not None:
                return await async_callable(self.backup)
            raise

    async def close(self) -> None:
        """Close both primary and backup clients.

        Safe to call multiple times (idempotent).
        """
        if self.primary is not None:
            await self.primary.aclose()
            self.primary = None

        if self.backup is not None:
            await self.backup.aclose()
            self.backup = None

        self._initialised = False

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}("
            f"primary_url={self.primary_url!r}, "
            f"backup_url={self.backup_url!r})"
        )


# ------------------------------------------------------------------
# Module-level helpers (backward-compatible replacements)
# ------------------------------------------------------------------

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
