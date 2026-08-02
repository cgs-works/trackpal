"""Bounded local execution state for the standalone lookup executor."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Literal, Protocol
from uuid import UUID

from app.callback_client import CallbackClient
from app.config import ExecutorSettings
from app.netflix import NetflixResolver
from app.pipeline.models import LookupCommand, LookupOutcome
from app.pipeline.runner import execute_lookup
from app.providers import GmailImapProvider

Pipeline = Callable[[LookupCommand], Awaitable[LookupOutcome]]
AcceptanceStatus = Literal["accepted", "duplicate", "conflict", "busy"]
logger = logging.getLogger(__name__)


class CallbackSender(Protocol):
    """Callback port used after local execution completes."""

    async def send(
        self,
        callback_url: str,
        *,
        job_id: UUID,
        lease_id: UUID,
        outcome: LookupOutcome,
    ) -> bool:
        """Deliver an outcome and return whether the callback was acknowledged."""


@dataclass(frozen=True, slots=True)
class CallbackContext:
    """Identity and destination needed to deliver one execution result."""

    callback_url: str
    job_id: UUID
    lease_id: UUID


@dataclass(frozen=True, slots=True)
class Acceptance:
    """Result of reserving a local execution slot."""

    accepted: bool
    lease_id: UUID
    status: AcceptanceStatus


class ExecutorRuntime:
    """Track active leases and execute commands within local capacity."""

    def __init__(
        self,
        settings: ExecutorSettings,
        *,
        pipeline: Pipeline | None = None,
        callback_client: CallbackSender | None = None,
    ) -> None:
        self.settings = settings
        self.capacity = settings.max_concurrency
        self._pipeline = pipeline or _production_pipeline
        self._callback_client = callback_client or CallbackClient(settings)
        self._lock = asyncio.Lock()
        self._active: dict[UUID, UUID] = {}

    @property
    def active_jobs(self) -> dict[UUID, UUID]:
        """Return a snapshot of active job-to-lease reservations."""
        return self._active.copy()

    async def accept(
        self,
        command: LookupCommand,
        callback_context: CallbackContext,
    ) -> Acceptance:
        """Validate and reserve a command before returning an HTTP acceptance."""
        if command.job_id is None or command.lease_id is None:
            raise ValueError("job_id and lease_id are required")
        if command.callback_url is None:
            raise ValueError("callback_url is required")
        if callback_context.job_id != command.job_id:
            raise ValueError("callback job_id does not match command")
        if callback_context.lease_id != command.lease_id:
            raise ValueError("callback lease_id does not match command")
        if callback_context.callback_url != command.callback_url:
            raise ValueError("callback URL does not match command")

        async with self._lock:
            current_lease = self._active.get(command.job_id)
            if current_lease is not None:
                status: AcceptanceStatus = (
                    "duplicate" if current_lease == command.lease_id else "conflict"
                )
                return Acceptance(
                    accepted=False,
                    lease_id=current_lease,
                    status=status,
                )
            if len(self._active) >= self.capacity:
                return Acceptance(
                    accepted=False,
                    lease_id=command.lease_id,
                    status="busy",
                )
            self._active[command.job_id] = command.lease_id
            return Acceptance(
                accepted=True,
                lease_id=command.lease_id,
                status="accepted",
            )

    async def execute(
        self,
        command: LookupCommand,
        callback_context: CallbackContext,
    ) -> None:
        """Run a reserved command, callback its outcome, and release its slot."""
        if command.job_id is None or command.lease_id is None:
            return
        try:
            try:
                outcome = await self._pipeline(command)
            except Exception:  # noqa: BLE001 - execution boundary is fail-safe
                outcome = LookupOutcome.terminal(
                    "executor_internal_error",
                    "Executor failed while processing the lookup",
                )
            try:
                await self._callback_client.send(
                    callback_context.callback_url,
                    job_id=command.job_id,
                    lease_id=command.lease_id,
                    outcome=outcome,
                )
            except Exception:  # noqa: BLE001 - callback failure is isolated
                logger.warning("lookup callback delivery failed")
        finally:
            await self._release(command.job_id, command.lease_id)

    async def _release(self, job_id: UUID, lease_id: UUID) -> None:
        async with self._lock:
            if self._active.get(job_id) == lease_id:
                del self._active[job_id]


async def _production_pipeline(command: LookupCommand) -> LookupOutcome:
    """Execute the worker's real provider-agnostic pipeline."""
    return await execute_lookup(command, GmailImapProvider(), NetflixResolver())


__all__ = [
    "Acceptance",
    "CallbackContext",
    "CallbackSender",
    "ExecutorRuntime",
]
