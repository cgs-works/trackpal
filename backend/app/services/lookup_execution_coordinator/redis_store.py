"""Redis implementation of lookup execution coordination."""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from app.core.config import settings
from app.core.encryption import get_fernet
from app.core.redis_client import RedisConnectionManager

from .types import LookupLease

QUEUE_KEY = "mailbox:lookup:queue"
QUEUE_SEEN_KEY = "mailbox:lookup:queue:seen"
DISPATCH_LOCK_PREFIX = "lookup:dispatch-lock:"
LEASE_PREFIX = "lookup:lease:"
EXECUTOR_LEASES_PREFIX = "lookup:executor-leases:"
CALLBACK_NONCE_PREFIX = "lookup:callback-nonce:"
RESULT_PREFIX = "lookup:result:"
EXECUTOR_COOLDOWN_PREFIX = "lookup:executor-cooldown:"

_ENQUEUE_SCRIPT = """
local added = redis.call('SADD', KEYS[1], ARGV[1])
if added == 1 then
    redis.call('RPUSH', KEYS[2], ARGV[1])
end
return added
"""
_POP_SCRIPT = """
local member = redis.call('LPOP', KEYS[1])
if member then
    redis.call('SREM', KEYS[2], member)
end
return member
"""
_RESERVE_LEASE_SCRIPT = """
local created = redis.call('SET', KEYS[1], ARGV[1], 'EX', ARGV[2], 'NX')
if not created then
    return 0
end
redis.call('ZADD', KEYS[2], ARGV[3], ARGV[4])
return 1
"""
_RELEASE_LEASE_SCRIPT = """
local payload = redis.call('GET', KEYS[1])
if not payload then
    return 0
end
local lease = cjson.decode(payload)
local executor_key = ARGV[1] .. lease.executor_id
redis.call('DEL', KEYS[1])
redis.call('ZREM', executor_key, ARGV[2])
return 1
"""


def _utc(value: datetime) -> datetime:
    """Normalize a timestamp to an aware UTC datetime."""
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _ttl_until(expires_at: datetime) -> int:
    """Return a Redis-compatible positive TTL for an absolute timestamp."""
    remaining = (_utc(expires_at) - datetime.now(timezone.utc)).total_seconds()
    return max(1, math.ceil(remaining))


class RedisLookupCoordinationStore:
    """Coordination store using the active failover-aware Redis manager."""

    def __init__(self, manager: RedisConnectionManager) -> None:
        self._manager = manager

    async def enqueue(self, job_id: UUID) -> bool:
        """Add a job to the queue only once until it is popped."""
        member = str(job_id)

        async def _enqueue(redis: Any) -> bool:
            result = await redis.eval(
                _ENQUEUE_SCRIPT,
                2,
                QUEUE_SEEN_KEY,
                QUEUE_KEY,
                member,
            )
            return bool(result)

        return bool(await self._manager.execute("lookup_enqueue", _enqueue))

    async def pop(self) -> UUID | None:
        """Remove and return the oldest queued job."""

        async def _pop(redis: Any) -> UUID | None:
            member = await redis.eval(
                _POP_SCRIPT,
                2,
                QUEUE_KEY,
                QUEUE_SEEN_KEY,
            )
            if member is None:
                return None
            return UUID(str(member))

        return await self._manager.execute("lookup_pop", _pop)

    async def acquire_dispatch_lock(self, job_id: UUID) -> bool:
        """Acquire a short-lived lock using Redis SET NX EX."""
        key = f"{DISPATCH_LOCK_PREFIX}{job_id}"

        async def _acquire(redis: Any) -> bool:
            result = await redis.set(
                key,
                "1",
                ex=max(1, settings.lookup_executor_handoff_timeout_seconds),
                nx=True,
            )
            return bool(result)

        return bool(await self._manager.execute("lookup_dispatch_lock", _acquire))

    async def release_dispatch_lock(self, job_id: UUID) -> None:
        """Release a dispatch lock."""
        key = f"{DISPATCH_LOCK_PREFIX}{job_id}"
        await self._manager.execute(
            "lookup_release_dispatch_lock", lambda r: r.delete(key)
        )

    async def reserve_lease(
        self,
        job_id: UUID,
        executor_id: UUID,
        lease_id: UUID,
        expires_at: datetime,
    ) -> bool:
        """Reserve a job lease and add it to the executor capacity set atomically."""
        expires_at = _utc(expires_at)
        if expires_at <= datetime.now(timezone.utc):
            return False
        payload = json.dumps(
            {
                "job_id": str(job_id),
                "executor_id": str(executor_id),
                "lease_id": str(lease_id),
                "expires_at": expires_at.isoformat(),
            },
            separators=(",", ":"),
        )
        lease_key = f"{LEASE_PREFIX}{job_id}"
        executor_key = f"{EXECUTOR_LEASES_PREFIX}{executor_id}"

        async def _reserve(redis: Any) -> bool:
            result = await redis.eval(
                _RESERVE_LEASE_SCRIPT,
                2,
                lease_key,
                executor_key,
                payload,
                str(_ttl_until(expires_at)),
                str(expires_at.timestamp()),
                str(job_id),
            )
            return bool(result)

        return bool(await self._manager.execute("lookup_reserve_lease", _reserve))

    async def get_lease(self, job_id: UUID) -> LookupLease | None:
        """Read and decode an active job lease."""
        key = f"{LEASE_PREFIX}{job_id}"

        async def _get(redis: Any) -> LookupLease | None:
            raw = await redis.get(key)
            if raw is None:
                return None
            value = json.loads(raw)
            expires_at = _utc(datetime.fromisoformat(value["expires_at"]))
            if expires_at <= datetime.now(timezone.utc):
                return None
            return LookupLease(
                job_id=UUID(str(value["job_id"])),
                executor_id=UUID(str(value["executor_id"])),
                lease_id=UUID(str(value["lease_id"])),
                expires_at=expires_at,
            )

        return await self._manager.execute("lookup_get_lease", _get)

    async def release_lease(self, job_id: UUID) -> None:
        """Delete a lease and remove its capacity marker atomically."""
        lease_key = f"{LEASE_PREFIX}{job_id}"

        async def _release(redis: Any) -> None:
            await redis.eval(
                _RELEASE_LEASE_SCRIPT,
                1,
                lease_key,
                EXECUTOR_LEASES_PREFIX,
                str(job_id),
            )

        await self._manager.execute("lookup_release_lease", _release)

    async def active_count(self, executor_id: UUID) -> int:
        """Prune expired sorted-set members and return active capacity."""
        key = f"{EXECUTOR_LEASES_PREFIX}{executor_id}"
        now = datetime.now(timezone.utc).timestamp()

        async def _count(redis: Any) -> int:
            await redis.zremrangebyscore(key, float("-inf"), now)
            return int(await redis.zcard(key))

        return int(await self._manager.execute("lookup_active_count", _count))

    async def consume_callback_nonce(
        self, executor_id: UUID, nonce: str, ttl_seconds: int
    ) -> bool:
        """Atomically consume a callback nonce with SET NX EX."""
        key = f"{CALLBACK_NONCE_PREFIX}{executor_id}:{nonce}"

        async def _consume(redis: Any) -> bool:
            result = await redis.set(key, "1", ex=max(1, ttl_seconds), nx=True)
            return bool(result)

        return bool(await self._manager.execute("lookup_callback_nonce", _consume))

    async def put_result(
        self, job_id: UUID, result_type: str, result_value: str, ttl_seconds: int
    ) -> None:
        """Encrypt and store an expiring result as one Fernet token."""
        payload = json.dumps(
            {"result_type": result_type, "result_value": result_value},
            separators=(",", ":"),
        )
        token = get_fernet().encrypt(payload.encode()).decode()
        key = f"{RESULT_PREFIX}{job_id}"
        await self._manager.execute(
            "lookup_put_result",
            lambda redis: redis.set(key, token, ex=max(1, ttl_seconds)),
        )

    async def get_result(self, job_id: UUID) -> tuple[str, str] | None:
        """Decrypt and return an unexpired result."""
        key = f"{RESULT_PREFIX}{job_id}"

        async def _get(redis: Any) -> tuple[str, str] | None:
            token = await redis.get(key)
            if token is None:
                return None
            payload = json.loads(get_fernet().decrypt(token.encode()).decode())
            return str(payload["result_type"]), str(payload["result_value"])

        return await self._manager.execute("lookup_get_result", _get)

    async def set_failure_cooldown(self, executor_id: UUID, ttl_seconds: int) -> None:
        """Start an executor failure cooldown."""
        key = f"{EXECUTOR_COOLDOWN_PREFIX}{executor_id}"
        await self._manager.execute(
            "lookup_set_failure_cooldown",
            lambda redis: redis.set(key, "1", ex=max(1, ttl_seconds)),
        )

    async def is_failure_cooldown_active(self, executor_id: UUID) -> bool:
        """Return whether the cooldown marker exists."""
        key = f"{EXECUTOR_COOLDOWN_PREFIX}{executor_id}"
        return bool(
            await self._manager.execute(
                "lookup_is_failure_cooldown_active", lambda redis: redis.get(key)
            )
        )

    async def clear_failure_cooldown(self, executor_id: UUID) -> None:
        """Clear an executor failure cooldown."""
        key = f"{EXECUTOR_COOLDOWN_PREFIX}{executor_id}"
        await self._manager.execute(
            "lookup_clear_failure_cooldown", lambda redis: redis.delete(key)
        )


__all__ = [
    "CALLBACK_NONCE_PREFIX",
    "DISPATCH_LOCK_PREFIX",
    "EXECUTOR_COOLDOWN_PREFIX",
    "EXECUTOR_LEASES_PREFIX",
    "LEASE_PREFIX",
    "QUEUE_KEY",
    "QUEUE_SEEN_KEY",
    "RESULT_PREFIX",
    "RedisLookupCoordinationStore",
]
