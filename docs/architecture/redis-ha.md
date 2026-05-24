# Redis High-Availability with Circuit-Breaker Failover

Manages ephemeral state for the WhatsApp Master and Tenant consoles using an active-passive Redis architecture with automatic failover.

## Architecture

```
[WhatsAppSessionService] ─→ [RedisConnectionManager.execute()]
         (Master: session:{phone}, Tenant: session:admin:{phone})
                                    │
                          ┌─────────┴──────────┐
                          │                    │
                    [Primary Redis]      [Backup Redis]
                    (active store)       (failover target)
                          │
               [FailoverPolicy]
               (circuit breaker)
```

## Connection Manager (`app/core/redis_client/`)

`RedisConnectionManager` owns exactly one primary and one backup Redis client, each backed by a connection pool.

### `execute(operation_name, async_callable)`

The primary method for all Redis operations. Routes the callable to the active store based on failover state:

- **CLOSED** → primary
- **OPEN** → backup
- **HALF_OPEN** → primary (probe), fall back to backup on failure

### Failover Policy (`FailoverPolicy`)

Three-state circuit breaker:

| State | Meaning | Behavior |
|-------|---------|----------|
| CLOSED | Primary active | All ops go to primary |
| OPEN | Backup active | After N consecutive primary failures; N = 3 (configurable) |
| HALF_OPEN | Probing primary | After open window expires (30s); next real op tests primary |

Events:
- `record_success()` — Resets failure counter; closes breaker from half-open
- `record_failure()` — Increments counter; opens breaker at threshold

### Client Configuration

Settings from env / `.env`:
- `REDIS_PRIMARY_URL` / `REDIS_BACKUP_URL` — `redis://` or `rediss://` URLs
- `REDIS_POOL_SIZE` — default 20
- `REDIS_SOCKET_TIMEOUT_SECONDS` — default 5.0
- `REDIS_HEALTH_CHECK_INTERVAL_SECONDS` — default 30.0
- `REDIS_FAILOVER_FAILURE_THRESHOLD` — default 3
- `REDIS_BREAKER_OPEN_SECONDS` — default 30

## Module-Level Helpers

- `init_redis()` — Creates `RedisConnectionManager` from settings, called on FastAPI startup
- `close_redis()` — Closes all clients, called on FastAPI shutdown
- `get_redis()` — Returns active Redis client or None
- `get_redis_manager()` — Returns the `RedisConnectionManager` instance for services that need `execute()`

## Contingency Reply Policy (`app/services/contingency_reply_policy/`)

Two deterministic replies for degraded states:

- `SESSION_RESET` — Cache miss on backup during failover; includes a fresh inline menu so the active console can continue
- `TEMPORARY_UNAVAILABLE` — Both Redis stores unreachable; n8n relays this safe message to the user

## Exception Handling

`RedisUnavailableError` wraps all infrastructure failures (ConnectionError, TimeoutError, OSError, redis-py errors). The integrations endpoint catches these and returns HTTP 200 with `TEMPORARY_UNAVAILABLE` text, so n8n never receives HTTP 5xx.
