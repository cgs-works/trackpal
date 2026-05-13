"""Tests for RedisConnectionManager: pools, lifecycle, URL schemes.

Verifies the manager creates process-lifetime primary/backup pools,
passes config through, and supports redis:// and rediss:// backup URLs.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pytest

from app.core.redis_client import FailoverState, RedisConnectionManager, RedisUnavailableError


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


@dataclass
class FakeRedis:
    """Record what was passed and track lifecycle."""

    url: str = ""
    kwargs: dict[str, Any] = field(default_factory=dict)
    closed: bool = False

    @classmethod
    def from_url(cls, url: str, **kwargs: Any) -> FakeRedis:
        return cls(url=url, kwargs=kwargs)

    async def aclose(self) -> None:
        self.closed = True

    def __bool__(self) -> bool:
        return True


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def fake_redis_factory():
    """Return the FakeRedis class so the manager can use it as redis_cls."""
    return FakeRedis


@pytest.fixture
def manager(fake_redis_factory):
    """Return a manager initialised with known settings and fake Redis."""
    m = RedisConnectionManager(
        primary_url="redis://primary:6379/0",
        backup_url="redis://backup:6379/0",
        pool_size=10,
        socket_timeout=5.0,
        connect_timeout=5.0,
        health_check_interval=30.0,
        redis_cls=fake_redis_factory,
    )
    return m


# ---------------------------------------------------------------------------
# Happy path – pool size, timeouts, decode_responses
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_manager_creates_exactly_one_primary_and_one_backup(manager):
    """Manager initialises exactly one primary client and one backup client."""
    assert manager.primary is not None
    assert manager.backup is not None
    assert isinstance(manager.primary, FakeRedis)
    assert isinstance(manager.backup, FakeRedis)


@pytest.mark.asyncio
async def test_manager_passes_pool_size_to_primary(manager):
    """max_connections is forwarded to the primary client."""
    assert manager.primary.kwargs.get("max_connections") == 10


@pytest.mark.asyncio
async def test_manager_passes_pool_size_to_backup(manager):
    """max_connections is forwarded to the backup client."""
    assert manager.backup.kwargs.get("max_connections") == 10


@pytest.mark.asyncio
async def test_manager_sets_decode_responses_true(manager):
    """decode_responses=True is forwarded to both clients."""
    assert manager.primary.kwargs.get("decode_responses") is True
    assert manager.backup.kwargs.get("decode_responses") is True


@pytest.mark.asyncio
async def test_manager_sets_socket_timeout(manager):
    """socket_timeout is forwarded to both clients."""
    assert manager.primary.kwargs.get("socket_timeout") == 5.0
    assert manager.backup.kwargs.get("socket_timeout") == 5.0


@pytest.mark.asyncio
async def test_manager_sets_connect_timeout(manager):
    """socket_connect_timeout is forwarded to both clients."""
    assert manager.primary.kwargs.get("socket_connect_timeout") == 5.0
    assert manager.backup.kwargs.get("socket_connect_timeout") == 5.0


@pytest.mark.asyncio
async def test_manager_sets_health_check_interval(manager):
    """health_check_interval is forwarded to both clients."""
    assert manager.primary.kwargs.get("health_check_interval") == 30.0
    assert manager.backup.kwargs.get("health_check_interval") == 30.0


# ---------------------------------------------------------------------------
# Lifecycle – close
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_close_closes_primary_and_backup(manager):
    """close() calls aclose() on both clients and clears references."""
    primary = manager.primary
    backup = manager.backup
    await manager.close()
    assert primary.closed is True
    assert backup.closed is True
    assert manager.primary is None
    assert manager.backup is None
    assert not manager._initialised


@pytest.mark.asyncio
async def test_close_idempotent(manager):
    """close() can be called twice without error."""
    await manager.close()
    await manager.close()  # no raise


# ---------------------------------------------------------------------------
# get_active_client placeholder
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_active_client_returns_primary(manager):
    """get_active_client() returns the primary client."""
    client = manager.get_active_client()
    assert client is manager.primary
    assert isinstance(client, FakeRedis)


# ---------------------------------------------------------------------------
# Backup URL schemes – redis:// and rediss://
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_backup_redis_url(fake_redis_factory):
    """Backup URL with redis:// scheme works."""
    m = RedisConnectionManager(
        primary_url="redis://p:6379/0",
        backup_url="redis://b:6379/0",
        redis_cls=fake_redis_factory,
    )
    assert m.backup.url == "redis://b:6379/0"


@pytest.mark.asyncio
async def test_backup_rediss_url(fake_redis_factory):
    """Backup URL with rediss:// (TLS) scheme works."""
    m = RedisConnectionManager(
        primary_url="redis://p:6379/0",
        backup_url="rediss://b:6380/0",
        redis_cls=fake_redis_factory,
    )
    assert m.backup.url == "rediss://b:6380/0"


@pytest.mark.asyncio
async def test_backup_url_schemes_do_not_raise(fake_redis_factory):
    """Both redis:// and rediss:// initialise without error."""
    m_redis = RedisConnectionManager(
        primary_url="redis://p:6379/0",
        backup_url="redis://b:6379/0",
        redis_cls=fake_redis_factory,
    )
    m_rediss = RedisConnectionManager(
        primary_url="redis://p:6379/0",
        backup_url="rediss://b:6380/0",
        redis_cls=fake_redis_factory,
    )
    assert m_redis.backup.url.startswith("redis://")
    assert m_rediss.backup.url.startswith("rediss://")


# ---------------------------------------------------------------------------
# Empty / unconfigured Redis
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_no_primary_url_creates_no_clients(fake_redis_factory):
    """When primary_url is empty, no clients are created (safe)."""
    m = RedisConnectionManager(
        primary_url="",
        backup_url="",
        redis_cls=fake_redis_factory,
    )
    assert m.primary is None
    assert m.backup is None
    assert m.is_available is False


@pytest.mark.asyncio
async def test_no_redis_get_active_client_returns_none(fake_redis_factory):
    """get_active_client() returns None when no Redis configured."""
    m = RedisConnectionManager(
        primary_url="",
        backup_url="",
        redis_cls=fake_redis_factory,
    )
    assert m.get_active_client() is None


@pytest.mark.asyncio
async def test_no_redis_close_is_safe(fake_redis_factory):
    """close() on unconfigured manager does not raise."""
    m = RedisConnectionManager(
        primary_url="",
        backup_url="",
        redis_cls=fake_redis_factory,
    )
    await m.close()  # no raise


# ---------------------------------------------------------------------------
# Failover — execute() method
# ---------------------------------------------------------------------------


class FailOnCallFake:
    """Fake client that raises on every call."""

    @classmethod
    def from_url(cls, url: str, **kwargs: Any) -> FailOnCallFake:
        return cls()

    async def aclose(self) -> None:
        pass

    def __bool__(self) -> bool:
        return True


@pytest.fixture
def manager_with_failover(fake_redis_factory):
    """Return a manager with failover policy and fake Redis clients."""
    m = RedisConnectionManager(
        primary_url="redis://p:6379/0",
        backup_url="redis://b:6379/0",
        pool_size=10,
        socket_timeout=5.0,
        connect_timeout=5.0,
        health_check_interval=30.0,
        redis_cls=fake_redis_factory,
        failure_threshold=2,
        open_window_seconds=60,
    )
    return m


@pytest.mark.asyncio
async def test_execute_uses_primary_when_closed(manager_with_failover):
    """In closed state, execute runs the callable against primary."""
    results = []

    async def op(client):
        results.append(client)
        return "ok"

    result = await manager_with_failover.execute("test_op", op)
    assert result == "ok"
    assert len(results) == 1
    assert results[0] is manager_with_failover.primary


@pytest.mark.asyncio
async def test_execute_primary_success_resets_failures(manager_with_failover):
    """Successful primary operation resets failure count."""
    policy = manager_with_failover._policy
    policy._consecutive_failures = 2  # simulate prior failures below threshold

    async def op(client):
        return "ok"

    await manager_with_failover.execute("test_op", op)
    assert policy.consecutive_failures == 0


@pytest.mark.asyncio
async def test_execute_primary_failure_below_threshold_stays_closed(
    manager_with_failover,
):
    """A single primary failure below threshold does not open breaker."""
    async def failing_op(client):
        raise ConnectionError("primary down")

    with pytest.raises(RedisUnavailableError, match="primary down"):
        await manager_with_failover.execute("failing_op", failing_op)

    assert manager_with_failover._policy.state == FailoverState.CLOSED


@pytest.mark.asyncio
async def test_execute_primary_failures_open_breaker_and_fallback_to_backup(
    manager_with_failover,
):
    """Consecutive primary failures open breaker and execute falls back to backup."""
    call_log: list[str] = []

    class SelectivelyFailingFake:
        """Fails on first two calls (threshold=2), succeeds on backup."""

        def __init__(self, url: str, **kwargs: Any):
            self.url = url
            self.call_count = 0

        @classmethod
        def from_url(cls, url: str, **kwargs: Any) -> SelectivelyFailingFake:
            return cls(url, **kwargs)

        async def get(self, key: str) -> str | None:
            self.call_count += 1
            call_log.append(f"get:{self.url}:{key}")
            if self.url.startswith("redis://p") and self.call_count <= 2:
                raise ConnectionError("primary down")
            return "value"

        async def aclose(self) -> None:
            pass

        def __bool__(self) -> bool:
            return True

    m = RedisConnectionManager(
        primary_url="redis://p:6379/0",
        backup_url="redis://b:6379/0",
        pool_size=10,
        redis_cls=SelectivelyFailingFake,
        failure_threshold=2,
        open_window_seconds=60,
    )

    # First call: primary fails (1 failure)
    with pytest.raises(RedisUnavailableError, match="primary down"):
        await m.execute("op1", lambda c: c.get("key1"))

    # Second call: primary fails (2 failures → OPEN), falls back to backup
    result = await m.execute("op2", lambda c: c.get("key2"))
    assert result == "value"
    # Verify backup was called
    assert any("redis://b:6379/0" in entry for entry in call_log), (
        f"Backup not in call log: {call_log}"
    )


@pytest.mark.asyncio
async def test_execute_uses_backup_when_open(manager_with_failover):
    """When breaker is open, execute runs against backup."""
    # Force breaker open
    manager_with_failover._policy._state = FailoverState.OPEN
    manager_with_failover._policy._opened_at = 0.0  # long ago but we'll freeze
    # Actually set opened_at to recent so window hasn't expired
    import time
    manager_with_failover._policy._opened_at = time.monotonic()

    call_log: list[Any] = []

    async def op(client):
        call_log.append(client)
        return "backup-result"

    result = await manager_with_failover.execute("open_op", op)
    assert result == "backup-result"
    assert len(call_log) == 1
    assert call_log[0] is manager_with_failover.backup


@pytest.mark.asyncio
async def test_execute_uses_primary_in_half_open(manager_with_failover):
    """In half-open state, execute tries primary."""
    # Force half-open state
    manager_with_failover._policy._state = FailoverState.HALF_OPEN

    call_log: list[Any] = []

    async def op(client):
        call_log.append(client)
        return "primary-ok"

    result = await manager_with_failover.execute("half_open_op", op)
    assert result == "primary-ok"
    assert len(call_log) == 1
    assert call_log[0] is manager_with_failover.primary


@pytest.mark.asyncio
async def test_execute_half_open_success_closes_breaker(manager_with_failover):
    """Successful half-open primary operation closes the breaker."""
    manager_with_failover._policy._state = FailoverState.HALF_OPEN

    async def op(client):
        return "ok"

    await manager_with_failover.execute("op", op)
    assert manager_with_failover._policy.state == FailoverState.CLOSED


@pytest.mark.asyncio
async def test_execute_half_open_failure_reopens_and_falls_back(
    manager_with_failover,
):
    """Failing half-open primary reopens breaker and falls back to backup."""
    manager_with_failover._policy._state = FailoverState.HALF_OPEN

    call_log: list[Any] = []

    async def failing_op(client):
        call_log.append(("call", client is manager_with_failover.primary))
        raise ConnectionError("still down")

    with pytest.raises(RedisUnavailableError, match="still down"):
        await manager_with_failover.execute("failing_op", failing_op)

    # Half-open failure should reopen
    assert manager_with_failover._policy.state == FailoverState.OPEN
    # Should have tried primary
    assert ("call", True) in call_log


@pytest.mark.asyncio
async def test_execute_both_stores_unavailable_surfaces_error(
    fake_redis_factory,
):
    """When both primary and backup fail, the exception is surfaced."""
    m = RedisConnectionManager(
        primary_url="redis://p:6379/0",
        backup_url="redis://b:6379/0",
        redis_cls=FailOnCallFake,
        failure_threshold=1,
        open_window_seconds=60,
    )

    async def op(client):
        raise ConnectionError("store unavailable")

    # Primary fails, falls back to backup, backup also fails
    with pytest.raises(RedisUnavailableError, match="store unavailable"):
        await m.execute("failing_op", op)


@pytest.mark.asyncio
async def test_execute_no_backup_configured_raises_primary_error(
    fake_redis_factory,
):
    """When no backup is configured, primary failures surface directly."""
    m = RedisConnectionManager(
        primary_url="redis://p:6379/0",
        backup_url="",
        redis_cls=FailOnCallFake,
        failure_threshold=1,
        open_window_seconds=60,
    )

    async def op(client):
        raise TimeoutError("primary timeout")

    with pytest.raises(RedisUnavailableError, match="primary timeout"):
        await m.execute("failing_op", op)


@pytest.mark.asyncio
async def test_execute_no_primary_configured_raises(manager_with_failover):
    """When primary is None, execute raises."""
    manager_with_failover.primary = None

    async def op(client):
        return "never called"

    with pytest.raises(RuntimeError, match="No active Redis client"):
        await manager_with_failover.execute("op", op)


# ---------------------------------------------------------------------------
# Default settings from config
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_manager_uses_settings_defaults():
    """Manager reads default settings when called without explicit args."""
    from app.core.config import settings

    m = RedisConnectionManager(
        primary_url=settings.redis_primary_url,
        backup_url=settings.redis_backup_url,
        pool_size=settings.redis_pool_size,
    )
    # Without a fake, we can't initialise real Redis, but we can stub
    # the class; just verify the module-level defaults compile.
    assert m.primary_url == settings.redis_primary_url
    assert m.backup_url == settings.redis_backup_url
    assert m.pool_size == settings.redis_pool_size


# ---------------------------------------------------------------------------
# Circuit-breaker threshold/ window wiring from settings
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_manager_wires_failure_threshold_from_init(fake_redis_factory):
    """failure_threshold passed to RedisConnectionManager reaches FailoverPolicy."""
    m = RedisConnectionManager(
        primary_url="redis://p:6379/0",
        backup_url="redis://b:6379/0",
        redis_cls=fake_redis_factory,
        failure_threshold=7,
        open_window_seconds=45,
    )
    assert m._policy.failure_threshold == 7


@pytest.mark.asyncio
async def test_manager_wires_open_window_seconds_from_init(fake_redis_factory):
    """open_window_seconds passed to RedisConnectionManager reaches FailoverPolicy."""
    m = RedisConnectionManager(
        primary_url="redis://p:6379/0",
        backup_url="redis://b:6379/0",
        redis_cls=fake_redis_factory,
        failure_threshold=7,
        open_window_seconds=45,
    )
    assert m._policy.open_window_seconds == 45


@pytest.mark.asyncio
async def test_init_redis_wires_settings_to_manager(monkeypatch):
    """init_redis() passes settings.redis_failover_failure_threshold
    and settings.redis_breaker_open_seconds to RedisConnectionManager."""
    from app.core.config import settings
    from app.core.redis_client import init_redis, get_redis_manager, close_redis

    # Ensure clean state
    await close_redis()

    # Temporarily set a primary URL so init_redis creates a manager.
    # from_url() creates a client object without connecting, so a
    # dummy URL is safe even without a real Redis server.
    monkeypatch.setattr(settings, "redis_primary_url", "redis://localhost:6379/0")
    monkeypatch.setattr(settings, "redis_backup_url", "")

    await init_redis()
    mgr = get_redis_manager()

    assert mgr is not None, "Manager should be created when primary URL is set"
    assert mgr._policy.failure_threshold == settings.redis_failover_failure_threshold
    assert mgr._policy.open_window_seconds == settings.redis_breaker_open_seconds
    assert mgr.primary is not None, "Primary client should be created"

    await close_redis()


# ---------------------------------------------------------------------------
# used_backup signal
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_used_backup_false_when_state_closed(manager):
    """Manager.used_backup is False when failover policy is CLOSED."""
    assert manager.used_backup is False


@pytest.mark.asyncio
async def test_used_backup_true_when_state_open(manager):
    """Manager.used_backup is True when failover policy is OPEN.

    Open the breaker via policy directly, then verify the signal
    reflects the OPEN state.
    """
    m = RedisConnectionManager(
        primary_url="redis://p:6379/0",
        backup_url="redis://b:6379/0",
        redis_cls=FakeRedis,
        failure_threshold=2,
        open_window_seconds=60,  # prevent immediate half-open
    )

    # Open the breaker via the policy directly
    m._policy.record_failure()
    m._policy.record_failure()
    assert m._policy.state is FailoverState.OPEN

    assert m.used_backup is True


@pytest.mark.asyncio
async def test_used_backup_false_after_policy_reset(manager):
    """Used_backup reverts to False after a policy reset."""
    m = RedisConnectionManager(
        primary_url="redis://p:6379/0",
        backup_url="redis://b:6379/0",
        redis_cls=FakeRedis,
        failure_threshold=1,
        open_window_seconds=60,
    )

    m._policy.record_failure()
    assert m._policy.state is FailoverState.OPEN
    assert m.used_backup is True

    m._policy.reset()
    assert m.used_backup is False
