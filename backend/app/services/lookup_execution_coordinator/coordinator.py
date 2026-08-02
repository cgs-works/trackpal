"""Scheduling and handoff orchestration for external lookup executors."""

from __future__ import annotations

import asyncio
import os
from collections.abc import Awaitable, Callable
from contextlib import AbstractAsyncContextManager
from datetime import datetime, timedelta, timezone
from typing import Any, Protocol
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.encryption import decrypt_value
from app.models import LookupExecutor
from app.repositories import mailbox_config_repository, mailbox_lookup_repository
from app.repositories import lookup_executors_repository
from app.schemas.lookup_executor_protocol import HandoffStatus
from app.services.lookup_executor_transport import LookupExecutorTransport

from .selector import ExecutorCapacity, select_executor


class CoordinationStore(Protocol):
    """Subset of Redis coordination used by the dispatch pump."""

    async def enqueue(self, job_id: UUID) -> bool: ...
    async def pop(self) -> UUID | None: ...
    async def has_queued_jobs(self, excluding_job_id: UUID | None = None) -> bool: ...
    async def acquire_dispatch_lock(self, job_id: UUID) -> bool: ...
    async def release_dispatch_lock(self, job_id: UUID) -> None: ...

    async def reserve_lease(
        self,
        job_id: UUID,
        executor_id: UUID,
        lease_id: UUID,
        expires_at: datetime,
    ) -> bool: ...

    async def release_lease(self, job_id: UUID) -> None: ...
    async def active_count(self, executor_id: UUID) -> int: ...
    async def is_failure_cooldown_active(self, executor_id: UUID) -> bool: ...
    async def clear_failure_cooldown(self, executor_id: UUID) -> None: ...
    async def set_failure_cooldown(
        self, executor_id: UUID, ttl_seconds: int
    ) -> None: ...


TaskSpawner = Callable[[Awaitable[None]], Any]


class LookupExecutionCoordinator:
    """Pump pending jobs into trusted external lookup executors."""

    def __init__(
        self,
        session_factory: Callable[[], AbstractAsyncContextManager[AsyncSession]],
        coordination_store: CoordinationStore,
        transport: LookupExecutorTransport,
        *,
        callback_base_url: str | None = None,
        task_spawner: TaskSpawner = asyncio.create_task,
    ) -> None:
        self._session_factory = session_factory
        self._store = coordination_store
        self._transport = transport
        self._callback_base_url = (
            callback_base_url
            or os.getenv("TRACKPAL_PUBLIC_URL", "http://localhost:8000")
        ).rstrip("/")
        self._task_spawner = task_spawner
        self._pump_guard = asyncio.Lock()
        self._pump_task: Any = None
        self._last_selected_at: dict[UUID, datetime] = {}
        self._consecutive_failures: dict[UUID, int] = {}

    async def schedule(self, job_id: UUID) -> None:
        """Queue a job and start one short-lived dispatch pump if needed."""
        await self._store.enqueue(job_id)
        async with self._pump_guard:
            if self._pump_is_active():
                return
            self._start_pump_locked()

    def _start_pump_locked(self) -> None:
        """Spawn a pump while the pump guard is held."""
        coroutine = self._pump()
        try:
            self._pump_task = self._task_spawner(coroutine)
        except BaseException:
            coroutine.close()
            self._pump_task = None
            raise

    def _pump_is_active(self) -> bool:
        """Return whether a previously spawned pump is still running."""
        if self._pump_task is None:
            return False
        done = getattr(self._pump_task, "done", None)
        return not callable(done) or not done()

    async def _has_queued_jobs(self, excluding_job_id: UUID | None = None) -> bool:
        """Return whether the coordination store still contains queued work."""
        checker = getattr(self._store, "has_queued_jobs", None)
        if checker is None:
            return False
        return bool(await checker(excluding_job_id))

    async def _pump(self) -> None:
        """Dispatch a bounded batch and continue if its queue still has work."""
        restart = True
        try:
            for _ in range(max(1, settings.lookup_dispatch_batch_size)):
                job_id = await self._store.pop()
                if job_id is None:
                    return
                if not await self._dispatch(job_id):
                    restart = await self._has_queued_jobs(excluding_job_id=job_id)
                    return
        except asyncio.CancelledError:
            restart = False
            raise
        except BaseException:
            restart = False
            raise
        finally:
            async with self._pump_guard:
                remaining = restart and await self._has_queued_jobs()
                if remaining:
                    self._start_pump_locked()
                else:
                    self._pump_task = None

    async def _dispatch(self, job_id: UUID) -> bool:
        """Attempt one job and return whether the pump may process another."""
        if not await self._store.acquire_dispatch_lock(job_id):
            return True
        try:
            async with self._session_factory() as db:
                job = await mailbox_lookup_repository.get_job(db, job_id)
                if job is None or job.status != "pending":
                    return True

                executor = await self._select_executor(db)
                if executor is None:
                    await self._requeue(db, job_id)
                    return False
                self._last_selected_at[executor.id] = datetime.now(timezone.utc)

                lease_id = uuid4()
                expires_at = datetime.now(timezone.utc) + timedelta(
                    seconds=settings.lookup_execution_lease_seconds
                )
                if not await self._store.reserve_lease(
                    job_id, executor.id, lease_id, expires_at
                ):
                    await self._requeue(db, job_id)
                    return False

                try:
                    try:
                        envelope = await self._build_envelope(
                            db, job, executor, lease_id, expires_at
                        )
                    except Exception:
                        await self._store.release_lease(job_id)
                        await self._requeue(
                            db, job_id, "mailbox credential is unavailable"
                        )
                        await db.commit()
                        return False
                    try:
                        outcome = await self._transport.handoff(executor, envelope)
                    except Exception:
                        await self._handle_transport_failure(
                            db, job, executor, "executor handoff transport failed"
                        )
                        await self._store.release_lease(job_id)
                        await db.commit()
                        return False
                    return await self._handle_handoff(
                        db, job, executor, lease_id, outcome
                    )
                except Exception:
                    await self._store.release_lease(job_id)
                    raise
        finally:
            await self._store.release_dispatch_lock(job_id)

    async def _select_executor(self, db: AsyncSession) -> LookupExecutor | None:
        """Build capacity snapshots and select one eligible registry entry."""
        executors = await lookup_executors_repository.list_dispatchable(db)
        candidates: list[ExecutorCapacity] = []
        by_id: dict[UUID, LookupExecutor] = {}
        for executor in executors:
            if getattr(executor, "lifecycle_status", "active") != "active":
                continue
            if getattr(executor, "requires_reverification", False):
                continue
            if await self._store.is_failure_cooldown_active(executor.id):
                continue
            active_leases = await self._store.active_count(executor.id)
            candidates.append(
                ExecutorCapacity(
                    executor_id=executor.id,
                    active_leases=active_leases,
                    max_concurrency=executor.max_concurrency,
                    last_selected_at=self._last_selected_at.get(executor.id),
                )
            )
            by_id[executor.id] = executor
        selected = select_executor(candidates)
        return None if selected is None else by_id[selected.executor_id]

    async def _build_envelope(
        self,
        db: AsyncSession,
        job: Any,
        executor: LookupExecutor,
        lease_id: UUID,
        expires_at: datetime,
    ) -> dict[str, object]:
        """Load and decrypt the mailbox credential only for this handoff."""
        mailbox = await mailbox_config_repository.get_by_id(db, job.mailbox_id)
        app_password = (
            None if mailbox is None else decrypt_value(mailbox.app_password_encrypted)
        )
        if mailbox is None or not app_password:
            raise RuntimeError("mailbox credential is unavailable")
        callback_url = (
            f"{self._callback_base_url}/api/v1/integrations/executors/"
            f"{executor.id}/jobs/{job.id}/complete"
        )
        return {
            "job_id": job.id,
            "lease_id": lease_id,
            "lease_expires_at": expires_at,
            "callback_url": callback_url,
            "mailbox_email": mailbox.mailbox_email,
            "app_password": app_password,
            "service_key": job.service_key,
            "target_email": job.target_email,
            "window_minutes": settings.mailbox_lookup_window_minutes,
        }

    async def _handle_handoff(
        self,
        db: AsyncSession,
        job: Any,
        executor: LookupExecutor,
        lease_id: UUID,
        outcome: Any,
    ) -> bool:
        """Map the normalized transport result to durable state and health."""
        if (
            outcome.status
            in {
                HandoffStatus.ACCEPTED,
                HandoffStatus.DUPLICATE_SAME_LEASE,
            }
            and outcome.lease_id == lease_id
        ):
            job.executor_id = executor.id
            job.execution_attempts += 1
            await mailbox_lookup_repository.transition_status(db, job, "processing")
            self._consecutive_failures.pop(executor.id, None)
            await self._store.clear_failure_cooldown(executor.id)
            await lookup_executors_repository.update_health(db, executor, "healthy")
            await db.commit()
            return True

        if outcome.status is HandoffStatus.BUSY:
            await self._store.release_lease(job.id)
            await self._requeue(db, job.id)
            await db.commit()
            return False

        await self._store.release_lease(job.id)
        if outcome.status in {
            HandoffStatus.SECURITY_ERROR,
            HandoffStatus.PROTOCOL_ERROR,
        }:
            executor.requires_reverification = True
            await lookup_executors_repository.update_health(
                db, executor, "unreachable", outcome.safe_error
            )
            await self._requeue(db, job.id, outcome.safe_error)
            await db.commit()
            return False

        await self._handle_transport_failure(
            db,
            job,
            executor,
            outcome.safe_error or "executor handoff transport failed",
        )
        await db.commit()
        return False

    async def _handle_transport_failure(
        self,
        db: AsyncSession,
        job: Any,
        executor: LookupExecutor,
        error: str,
    ) -> None:
        """Record consecutive failures and leave the durable job pending."""
        failures = self._consecutive_failures.get(executor.id, 0) + 1
        self._consecutive_failures[executor.id] = failures
        health = "unreachable" if failures >= 3 else "degraded"
        await lookup_executors_repository.update_health(db, executor, health, error)
        if failures >= 3:
            await self._store.set_failure_cooldown(
                executor.id, settings.lookup_executor_failure_cooldown_seconds
            )
        await self._requeue(db, job.id, error)

    async def _requeue(
        self, db: AsyncSession, job_id: UUID, error: str | None = None
    ) -> None:
        """Put a popped job back in Redis without changing pending status."""
        job = await mailbox_lookup_repository.get_job(db, job_id)
        if job is not None and error is not None:
            job.last_dispatch_error_safe = error
            await db.flush()
        await self._store.enqueue(job_id)


__all__ = ["LookupExecutionCoordinator"]
