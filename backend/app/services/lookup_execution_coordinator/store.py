"""Protocol for lookup execution coordination backends."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol
from uuid import UUID

from .types import LookupLease


class LookupCoordinationStore(Protocol):
    """Durable queue and execution state used by the lookup coordinator."""

    async def enqueue(self, job_id: UUID) -> bool:
        """Add a pending job once and return whether it was newly queued."""
        ...

    async def pop(self) -> UUID | None:
        """Remove and return the next queued job, if one exists."""
        ...

    async def acquire_dispatch_lock(self, job_id: UUID) -> bool:
        """Acquire the short-lived dispatch lock for a job."""
        ...

    async def release_dispatch_lock(self, job_id: UUID) -> None:
        """Release a job's dispatch lock."""
        ...

    async def reserve_lease(
        self,
        job_id: UUID,
        executor_id: UUID,
        lease_id: UUID,
        expires_at: datetime,
    ) -> bool:
        """Reserve an execution lease when the job has no active lease."""
        ...

    async def get_lease(self, job_id: UUID) -> LookupLease | None:
        """Return a job's active lease, if any."""
        ...

    async def release_lease(self, job_id: UUID) -> None:
        """Remove a job lease and its executor capacity marker."""
        ...

    async def active_count(self, executor_id: UUID) -> int:
        """Return the number of unexpired leases held by an executor."""
        ...

    async def consume_callback_nonce(
        self, executor_id: UUID, nonce: str, ttl_seconds: int
    ) -> bool:
        """Atomically consume a callback nonce for its TTL window."""
        ...

    async def put_result(
        self, job_id: UUID, result_type: str, result_value: str, ttl_seconds: int
    ) -> None:
        """Store an encrypted, expiring execution result."""
        ...

    async def get_result(self, job_id: UUID) -> tuple[str, str] | None:
        """Return a decrypted result, if it has not expired."""
        ...

    async def set_failure_cooldown(self, executor_id: UUID, ttl_seconds: int) -> None:
        """Start or replace an executor failure cooldown."""
        ...

    async def is_failure_cooldown_active(self, executor_id: UUID) -> bool:
        """Return whether an executor is currently cooling down."""
        ...

    async def clear_failure_cooldown(self, executor_id: UUID) -> None:
        """Clear an executor failure cooldown."""
        ...


__all__ = ["LookupCoordinationStore"]
