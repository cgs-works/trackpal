"""Persistence operations for the Master-managed executor registry."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.encryption import encrypt_value
from app.models import LookupExecutor, MailLookupJob


_ACTIVE_JOB_STATUSES = ("pending", "processing")


def _active_jobs_count() -> Any:
    """Build a correlated count of non-terminal jobs for each executor."""
    return (
        select(func.count(MailLookupJob.id))
        .where(
            MailLookupJob.executor_id == LookupExecutor.id,
            MailLookupJob.status.in_(_ACTIVE_JOB_STATUSES),
        )
        .correlate(LookupExecutor)
        .scalar_subquery()
    )


def _set_active_jobs(executor: LookupExecutor, active_jobs: int) -> LookupExecutor:
    """Attach the query-derived active job count for response serialization."""
    executor.active_jobs = int(active_jobs)
    return executor


async def create(
    db: AsyncSession,
    executor: LookupExecutor | None = None,
    *,
    name: str | None = None,
    provider_label: str = "custom",
    base_url: str = "",
    transport_mode: str = "https",
    lifecycle_status: str = "draft",
    health_status: str = "unknown",
    requires_reverification: bool = False,
    max_concurrency: int = 1,
    secret: str | None = None,
    secret_encrypted: str | None = None,
    secret_version: int = 1,
    pending_secret: str | None = None,
    pending_secret_encrypted: str | None = None,
    pending_secret_version: int | None = None,
    hosting_account_email: str | None = None,
    hosting_account_password: str | None = None,
    hosting_account_password_encrypted: str | None = None,
    dashboard_url: str | None = None,
) -> LookupExecutor:
    """Create an executor, encrypting credentials before persistence.

    An already-built model is accepted for callers that have encrypted values
    prepared by a service. Plain credential keyword arguments are encrypted in
    this repository so they never reach SQLAlchemy as plaintext.
    """
    if executor is None:
        if name is None:
            raise ValueError("name is required")
        if secret is None and secret_encrypted is None:
            raise ValueError("secret or secret_encrypted is required")
        executor = LookupExecutor(
            name=name,
            provider_label=provider_label,
            base_url=base_url,
            transport_mode=transport_mode,
            lifecycle_status=lifecycle_status,
            health_status=health_status,
            requires_reverification=requires_reverification,
            max_concurrency=max_concurrency,
            secret_encrypted=secret_encrypted or encrypt_value(secret),
            secret_version=secret_version,
            pending_secret_encrypted=(
                pending_secret_encrypted or encrypt_value(pending_secret)
            ),
            pending_secret_version=pending_secret_version,
            hosting_account_email=hosting_account_email,
            hosting_account_password_encrypted=(
                hosting_account_password_encrypted
                or encrypt_value(hosting_account_password)
            ),
            dashboard_url=dashboard_url,
        )
    db.add(executor)
    await db.flush()
    return executor


async def get(db: AsyncSession, executor_id: UUID) -> LookupExecutor | None:
    """Return an executor by stable identifier with its active job count."""
    result = await db.execute(
        select(LookupExecutor, _active_jobs_count().label("active_jobs")).where(
            LookupExecutor.id == executor_id
        )
    )
    row = result.one_or_none()
    if row is None:
        return None
    executor, active_jobs = row
    return _set_active_jobs(executor, active_jobs)


async def list_all(db: AsyncSession) -> list[LookupExecutor]:
    """List all executors in stable creation order with active job counts."""
    result = await db.execute(
        select(LookupExecutor, _active_jobs_count().label("active_jobs")).order_by(
            LookupExecutor.created_at.asc()
        )
    )
    return [
        _set_active_jobs(executor, active_jobs)
        for executor, active_jobs in result.all()
    ]


async def list_dispatchable(db: AsyncSession) -> list[LookupExecutor]:
    """List active executors that are not quarantined for reverification."""
    result = await db.execute(
        select(LookupExecutor, _active_jobs_count().label("active_jobs"))
        .where(
            LookupExecutor.lifecycle_status == "active",
            LookupExecutor.requires_reverification.is_(False),
        )
        .order_by(LookupExecutor.created_at.asc())
    )
    return [
        _set_active_jobs(executor, active_jobs)
        for executor, active_jobs in result.all()
    ]


async def update(
    db: AsyncSession, executor: LookupExecutor, **fields: Any
) -> LookupExecutor:
    """Update registry metadata, encrypting supplied credential values."""
    for field, value in fields.items():
        if field == "secret":
            field = "secret_encrypted"
            value = encrypt_value(value)
        elif field == "pending_secret":
            field = "pending_secret_encrypted"
            value = encrypt_value(value)
        elif field == "hosting_account_password":
            field = "hosting_account_password_encrypted"
            value = encrypt_value(value)
        if not hasattr(LookupExecutor, field):
            raise ValueError(f"Unknown executor field: {field}")
        setattr(executor, field, value)
    await db.flush()
    return executor


async def update_lifecycle_status(
    db: AsyncSession, executor: LookupExecutor, status: str
) -> LookupExecutor:
    """Set the executor lifecycle status."""
    executor.lifecycle_status = status
    await db.flush()
    return executor


async def update_health(
    db: AsyncSession,
    executor: LookupExecutor,
    status: str,
    error: str | None = None,
) -> LookupExecutor:
    """Record health status and safe operational error metadata."""
    executor.health_status = status
    executor.last_health_check_at = datetime.now(timezone.utc)
    executor.last_error_safe = error
    if status == "healthy":
        executor.last_success_at = executor.last_health_check_at
    await db.flush()
    return executor


async def set_pending_secret(
    db: AsyncSession,
    executor: LookupExecutor,
    secret: str,
    version: int,
) -> LookupExecutor:
    """Store an encrypted candidate secret until it is verified."""
    executor.pending_secret_encrypted = encrypt_value(secret)
    executor.pending_secret_version = version
    await db.flush()
    return executor


async def promote_pending_secret(
    db: AsyncSession, executor: LookupExecutor
) -> LookupExecutor:
    """Promote a verified pending secret atomically in the current transaction."""
    if (
        executor.pending_secret_encrypted is None
        or executor.pending_secret_version is None
    ):
        raise ValueError("No pending secret to promote")
    executor.secret_encrypted = executor.pending_secret_encrypted
    executor.secret_version = executor.pending_secret_version
    executor.pending_secret_encrypted = None
    executor.pending_secret_version = None
    executor.requires_reverification = False
    await db.flush()
    return executor


async def delete(db: AsyncSession, executor: LookupExecutor) -> None:
    """Delete an executor registry row."""
    await db.delete(executor)
    await db.flush()


__all__ = [
    "create",
    "get",
    "list_all",
    "list_dispatchable",
    "update",
    "update_lifecycle_status",
    "update_health",
    "set_pending_secret",
    "promote_pending_secret",
    "delete",
]
