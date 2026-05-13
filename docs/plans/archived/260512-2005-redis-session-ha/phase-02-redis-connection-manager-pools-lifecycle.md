# Phase 2: Redis Connection Manager, Pools, and Lifecycle

**Complexity:** M  
**Dependencies:** Phase 1

## Objective

Replace the current single Redis client helper with a process-lifetime active-passive Redis connection manager that owns one primary pool and one backup pool, supports configurable capacity/timeouts, and accepts `redis://` or `rediss://` backup URLs.

## Preconditions

- Phone canonicalization is complete and tests are green.
- `backend/app/core/redis_client.py` currently provides `init_redis()`, `close_redis()`, and `get_redis()` for FastAPI lifespan usage.

## Tasks

1. Inspect `redis.asyncio.Redis.from_url` options for connection pool size, socket timeout, connect timeout, health check interval, and URL scheme support already available through the installed Redis client.
2. Update `backend/app/core/config.py` with settings for `redis_primary_url`, `redis_backup_url`, `redis_pool_size`, `redis_socket_timeout_seconds`, `redis_connect_timeout_seconds`, `redis_health_check_interval_seconds`, `redis_failover_failure_threshold`, `redis_breaker_open_seconds`, and `whatsapp_session_ttl_minutes=15`.
3. Preserve backward compatibility by treating existing `redis_url` as primary if `redis_primary_url` is absent, unless project convention favors a direct rename with deployment doc updates.
4. Implement `RedisConnectionManager` in `backend/app/core/redis_client.py` or a focused new module imported by that file.
5. Ensure the manager initializes at most one primary Redis client/pool and at most one backup Redis client/pool per process.
6. Configure each client with `max_connections=settings.redis_pool_size`, decode responses, short socket/connect timeouts, and health check interval.
7. Validate backup URL schemes by accepting both `redis://` and `rediss://`; do not special-case TLS elsewhere.
8. Make `init_redis()` initialize the manager and keep the public lifespan call in `backend/app/main.py` stable where possible.
9. Make `close_redis()` close both primary and backup clients and clear process-level references.
10. Add a manager method such as `get_active_client()` or `execute()` placeholder that Phase 3 can extend with failover; for this phase it may return primary when available.
11. Update `backend/app/api/v1/endpoints/integrations.py` and any direct imports so they depend on the manager abstraction instead of a single optional Redis client where practical.
12. Add `backend/tests/test_redis_connection_manager.py` with fake Redis factory/client objects to verify one primary and one backup are created, no client is created per request, configured options are passed, and shutdown closes both clients.
13. Add tests proving backup URL can be `redis://` or `rediss://` through configuration/factory inputs.
14. Add tests proving no Redis configured still yields the same safe unavailable behavior for the WhatsApp console endpoint.

## Verification

- Commands:
  - `cd backend && uv run pytest tests/test_redis_connection_manager.py -v`
  - `cd backend && uv run pytest tests/test_whatsapp_endpoint.py -v`
  - `cd backend && uv run pytest -v`
- Expected results:
  - The manager creates reusable process-lifetime clients/pools, not request-scoped clients.
  - Both primary and backup clients are closed during shutdown.
  - Pool size and timeout settings are passed to Redis client construction.
  - Backup supports `redis://` and `rediss://` via config.
  - Existing endpoint behavior remains safe when Redis is not configured.

## Exit Criteria

- Redis access is centralized behind a connection manager with primary and backup pool lifecycle.
- FastAPI lifespan initializes and closes all Redis resources.
- Pool sizing and timeout behavior are configurable.
- No product behavior uses active-active or double-write Redis access.
