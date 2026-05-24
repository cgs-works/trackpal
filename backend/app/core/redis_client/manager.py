"""Redis connection manager with active-passive primary/backup pools."""

from __future__ import annotations

from typing import Any

from .policy import FailoverPolicy
from .types import FailoverState, RedisUnavailableError, is_redis_infra_error


class RedisConnectionManager:
    """Active-passive Redis connection manager with circuit-breaker failover.

    Owns exactly one primary and one backup ``Redis`` client (each backed
    by a ``ConnectionPool``) for the process lifetime.

    Operations are routed through :meth:`execute`, which uses a
    :class:`FailoverPolicy` to decide whether to use primary or backup,
    records successes/failures, and falls back to backup when the
    breaker opens.
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
            self.primary = self._redis_cls.from_url(self.primary_url, **common_kwargs)
        if self.backup_url:
            self.backup = self._redis_cls.from_url(self.backup_url, **common_kwargs)
        self._initialised = True

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
        """Return the currently active Redis client using the failover policy."""
        if self._policy.should_use_backup():
            return self.backup
        return self.primary

    async def execute(self, operation_name: str, async_callable: Any) -> Any:
        """Run *async_callable(client)* on the active Redis store.

        The callable receives the active Redis client determined by the
        failover policy.

        * Primary success resets failures.
        * Primary failure records the failure and, if the breaker opens,
          retries on backup when available.
        * Backup failures surface as-is.

        Raises
        ------
        RuntimeError
            When no Redis client is configured.
        RedisUnavailableError
            When the active Redis store raises a connection/timeout/OS
            or generic Redis error.
        """
        self._policy._check_open_window()
        state = self._policy.state
        try:
            if state is FailoverState.CLOSED:
                return await self._execute_primary(operation_name, async_callable)
            if state is FailoverState.OPEN:
                return await self._execute_backup(operation_name, async_callable)
            return await self._execute_half_open(operation_name, async_callable)
        except RuntimeError:
            raise
        except Exception as exc:
            if is_redis_infra_error(exc):
                raise RedisUnavailableError(str(exc)) from exc
            raise

    async def _execute_primary(self, operation_name: str, async_callable: Any) -> Any:
        """Try primary; on failure record it and possibly fall back."""
        if self.primary is None:
            raise RuntimeError("No active Redis client (primary not configured)")
        try:
            result = await async_callable(self.primary)
            self._policy.record_success()
            return result
        except Exception as exc:
            if not is_redis_infra_error(exc):
                raise
            self._policy.record_failure()
            if self._policy.state is FailoverState.OPEN and self.backup is not None:
                return await async_callable(self.backup)
            raise

    async def _execute_backup(self, operation_name: str, async_callable: Any) -> Any:
        """Run the operation against backup.  Failures surface as-is."""
        if self.backup is None:
            raise RuntimeError("No active Redis client (backup not configured)")
        return await async_callable(self.backup)

    async def _execute_half_open(self, operation_name: str, async_callable: Any) -> Any:
        """Probe primary in half-open state."""
        if self.primary is None:
            raise RuntimeError("No active Redis client (primary not configured)")
        try:
            result = await async_callable(self.primary)
            self._policy.record_success()
            return result
        except Exception as exc:
            if not is_redis_infra_error(exc):
                raise
            self._policy.record_failure()
            if self.backup is not None:
                return await async_callable(self.backup)
            raise

    async def close(self) -> None:
        """Close both primary and backup clients (idempotent)."""
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
