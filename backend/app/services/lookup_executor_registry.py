"""Lifecycle service for Master-managed external lookup executors."""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any, Protocol
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import LookupExecutor
from app.repositories import lookup_executors_repository
from app.schemas.lookup_executor_protocol import ChallengeResult
from app.services.lookup_executor_transport import (
    HttpLookupExecutorTransport,
    LookupExecutorTransport,
    TransportError,
)
from app.services.lookup_executor_transport.url_safety import ExecutorUrlError


class ExecutorCoordinationUnavailable(RuntimeError):
    """Raised when active Redis execution leases cannot be inspected."""


class ActiveLeaseReader(Protocol):
    """Port supplied by Redis coordination to inspect executor leases."""

    async def active_count(self, executor_id: UUID) -> int:
        """Return the number of active execution leases."""
        ...


class UnavailableActiveLeaseReader:
    """Production placeholder until the Redis coordination store is wired."""

    async def active_count(self, executor_id: UUID) -> int:
        """Fail closed instead of allowing an unsafe deletion."""
        del executor_id
        raise ExecutorCoordinationUnavailable


@dataclass(frozen=True)
class ExecutorVerificationError(Exception):
    """Safe internal error for an unsuccessful executor challenge."""

    code: str = "executor_verification_failed"

    def __str__(self) -> str:
        return self.code


_transport: LookupExecutorTransport = HttpLookupExecutorTransport()
_active_lease_reader: ActiveLeaseReader = UnavailableActiveLeaseReader()


def _candidate_with_secret(executor: Any, encrypted: str, version: int) -> Any:
    """Make a transport-only executor view for a pending key candidate."""
    return SimpleNamespace(
        id=executor.id,
        base_url=executor.base_url,
        transport_mode=executor.transport_mode,
        max_concurrency=executor.max_concurrency,
        secret_encrypted=encrypted,
        secret_version=version,
    )


async def _challenge(
    executor: Any,
    *,
    use_pending: bool = False,
) -> ChallengeResult:
    """Challenge one stored key and normalize all transport failures."""
    candidate = executor
    if use_pending:
        if (
            executor.pending_secret_encrypted is None
            or executor.pending_secret_version is None
        ):
            raise ExecutorVerificationError
        candidate = _candidate_with_secret(
            executor,
            executor.pending_secret_encrypted,
            executor.pending_secret_version,
        )

    try:
        result = await _transport.challenge(candidate, secrets.token_urlsafe(24))
    except (ExecutorUrlError, TransportError, ValueError, TypeError, OSError) as exc:
        raise ExecutorVerificationError from exc
    except Exception as exc:
        # Adapter implementations must not leak raw network or protocol errors.
        raise ExecutorVerificationError from exc

    if result.executor_id != executor.id or result.protocol_version != 1:
        raise ExecutorVerificationError
    return result


async def create_executor(
    db: AsyncSession, **fields: Any
) -> tuple[LookupExecutor, str]:
    """Create a draft and return its generated protocol secret exactly once."""
    plain_secret = secrets.token_urlsafe(32)
    executor = await lookup_executors_repository.create(
        db,
        name=fields["name"],
        provider_label=fields["provider_label"],
        base_url=fields.get("base_url", ""),
        transport_mode=fields.get("transport_mode", "https"),
        max_concurrency=fields.get("max_concurrency", 1),
        hosting_account_email=fields.get("hosting_account_email"),
        hosting_account_password=fields.get("hosting_account_password"),
        dashboard_url=fields.get("dashboard_url"),
        secret=plain_secret,
    )
    return executor, plain_secret


async def verify_executor(
    db: AsyncSession, executor: LookupExecutor, confirmation: str | None
) -> LookupExecutor:
    """Challenge an executor and activate or promote its verified key."""
    if executor.transport_mode == "http_encrypted" and confirmation != "ALLOW HTTP":
        raise ValueError("insecure_http_confirmation_required")

    use_pending = executor.pending_secret_encrypted is not None
    try:
        await _challenge(executor, use_pending=use_pending)
    except ExecutorVerificationError:
        await lookup_executors_repository.update_health(
            db, executor, "unhealthy", "executor verification failed"
        )
        executor.requires_reverification = True
        executor.last_verified_at = None
        await db.flush()
        raise

    if use_pending:
        await lookup_executors_repository.promote_pending_secret(db, executor)
    else:
        executor.requires_reverification = False
    executor.last_verified_at = datetime.now(timezone.utc)
    executor.lifecycle_status = "active"
    await lookup_executors_repository.update_health(db, executor, "healthy")
    await db.flush()
    return executor


async def test_executor(db: AsyncSession, executor: LookupExecutor) -> ChallengeResult:
    """Check executor connectivity without establishing verification state."""
    try:
        result = await _challenge(executor)
    except ExecutorVerificationError:
        await lookup_executors_repository.update_health(
            db, executor, "unhealthy", "executor verification failed"
        )
        executor.requires_reverification = True
        executor.last_verified_at = None
        await db.flush()
        raise
    await lookup_executors_repository.update_health(db, executor, "healthy")
    return result


async def rotate_secret(
    db: AsyncSession, executor: LookupExecutor
) -> tuple[LookupExecutor, str]:
    """Create an encrypted pending protocol key without activating it."""
    plain_secret = secrets.token_urlsafe(32)
    await lookup_executors_repository.set_pending_secret(
        db, executor, plain_secret, executor.secret_version + 1
    )
    return executor, plain_secret


async def delete_executor(db: AsyncSession, executor: LookupExecutor) -> None:
    """Delete only when both PostgreSQL jobs and Redis leases are idle."""
    if int(getattr(executor, "active_jobs", 0)) > 0:
        raise ValueError("executor_has_active_jobs")
    try:
        active_leases = await _active_lease_reader.active_count(executor.id)
    except ExecutorCoordinationUnavailable:
        raise
    except Exception as exc:
        raise ExecutorCoordinationUnavailable from exc
    if active_leases > 0:
        raise ValueError("executor_has_active_leases")
    await lookup_executors_repository.delete(db, executor)


async def reveal_hosting_password(executor: LookupExecutor) -> str:
    """Decrypt the optional hosting password only for a step-up request."""
    from app.core.encryption import decrypt_value

    password = decrypt_value(executor.hosting_account_password_encrypted)
    if password is None:
        raise ValueError("hosting_password_not_configured")
    return password


__all__ = [
    "ActiveLeaseReader",
    "ExecutorCoordinationUnavailable",
    "ExecutorVerificationError",
    "UnavailableActiveLeaseReader",
    "create_executor",
    "delete_executor",
    "reveal_hosting_password",
    "rotate_secret",
    "test_executor",
    "verify_executor",
]
