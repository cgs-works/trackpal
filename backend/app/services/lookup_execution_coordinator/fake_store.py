"""In-memory coordination store for tests and local service tests."""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from uuid import UUID

from app.core.config import settings
from app.core.encryption import get_fernet

from .types import LookupLease


def _utc(value: datetime) -> datetime:
    """Normalize a timestamp to an aware UTC datetime."""
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


class FakeLookupCoordinationStore:
    """Deterministic in-memory implementation of the coordination protocol."""

    def __init__(self) -> None:
        self._queue: list[UUID] = []
        self._queued: set[UUID] = set()
        self._dispatch_locks: dict[UUID, float] = {}
        self._leases: dict[UUID, LookupLease] = {}
        self._nonces: dict[tuple[UUID, str], float] = {}
        self._results: dict[UUID, tuple[float, str]] = {}
        self._cooldowns: dict[UUID, float] = {}

    async def enqueue(self, job_id: UUID) -> bool:
        """Queue a job once until it is popped."""
        if job_id in self._queued:
            return False
        self._queued.add(job_id)
        self._queue.append(job_id)
        return True

    async def pop(self) -> UUID | None:
        """Pop the oldest queued job."""
        if not self._queue:
            return None
        job_id = self._queue.pop(0)
        self._queued.discard(job_id)
        return job_id

    async def has_queued_jobs(self, excluding_job_id: UUID | None = None) -> bool:
        """Return whether queued work remains, optionally excluding one job."""
        return any(job_id != excluding_job_id for job_id in self._queue)

    async def acquire_dispatch_lock(self, job_id: UUID) -> bool:
        """Acquire a short-lived dispatch lock if it is not already held."""
        now = time.monotonic()
        expires_at = self._dispatch_locks.get(job_id)
        if expires_at is not None and expires_at > now:
            return False
        self._dispatch_locks[job_id] = (
            now + settings.lookup_executor_handoff_timeout_seconds
        )
        return True

    async def release_dispatch_lock(self, job_id: UUID) -> None:
        """Release a dispatch lock."""
        self._dispatch_locks.pop(job_id, None)

    async def reserve_lease(
        self,
        job_id: UUID,
        executor_id: UUID,
        lease_id: UUID,
        expires_at: datetime,
    ) -> bool:
        """Reserve an unexpired lease for a job."""
        expires_at = _utc(expires_at)
        now = datetime.now(timezone.utc)
        if expires_at <= now:
            return False
        existing = self._leases.get(job_id)
        if existing is not None:
            if existing.expires_at > now:
                return False
            self._leases.pop(job_id, None)
        self._leases[job_id] = LookupLease(job_id, executor_id, lease_id, expires_at)
        return True

    async def get_lease(self, job_id: UUID) -> LookupLease | None:
        """Return an unexpired lease."""
        lease = self._leases.get(job_id)
        if lease is None:
            return None
        if lease.expires_at <= datetime.now(timezone.utc):
            self._leases.pop(job_id, None)
            return None
        return lease

    async def release_lease(self, job_id: UUID) -> None:
        """Release a job lease."""
        self._leases.pop(job_id, None)

    async def active_count(self, executor_id: UUID) -> int:
        """Count unexpired leases for an executor."""
        now = datetime.now(timezone.utc)
        expired = [
            job_id for job_id, lease in self._leases.items() if lease.expires_at <= now
        ]
        for job_id in expired:
            self._leases.pop(job_id, None)
        return sum(lease.executor_id == executor_id for lease in self._leases.values())

    async def consume_callback_nonce(
        self, executor_id: UUID, nonce: str, ttl_seconds: int
    ) -> bool:
        """Consume a nonce once until its expiry."""
        key = (executor_id, nonce)
        now = time.monotonic()
        expires_at = self._nonces.get(key)
        if expires_at is not None and expires_at > now:
            return False
        self._nonces[key] = now + max(1, ttl_seconds)
        return True

    async def put_result(
        self, job_id: UUID, result_type: str, result_value: str, ttl_seconds: int
    ) -> None:
        """Encrypt and store a result until its TTL expires."""
        payload = json.dumps(
            {"result_type": result_type, "result_value": result_value},
            separators=(",", ":"),
        )
        token = get_fernet().encrypt(payload.encode()).decode()
        self._results[job_id] = (time.monotonic() + max(1, ttl_seconds), token)

    async def get_result(self, job_id: UUID) -> tuple[str, str] | None:
        """Decrypt and return a result that has not expired."""
        item = self._results.get(job_id)
        if item is None:
            return None
        expires_at, token = item
        if expires_at <= time.monotonic():
            self._results.pop(job_id, None)
            return None
        payload = json.loads(get_fernet().decrypt(token.encode()).decode())
        return str(payload["result_type"]), str(payload["result_value"])

    async def set_failure_cooldown(self, executor_id: UUID, ttl_seconds: int) -> None:
        """Start an executor failure cooldown."""
        self._cooldowns[executor_id] = time.monotonic() + max(1, ttl_seconds)

    async def is_failure_cooldown_active(self, executor_id: UUID) -> bool:
        """Check and lazily expire an executor cooldown."""
        expires_at = self._cooldowns.get(executor_id)
        if expires_at is None:
            return False
        if expires_at <= time.monotonic():
            self._cooldowns.pop(executor_id, None)
            return False
        return True

    async def clear_failure_cooldown(self, executor_id: UUID) -> None:
        """Clear an executor failure cooldown."""
        self._cooldowns.pop(executor_id, None)


__all__ = ["FakeLookupCoordinationStore"]
