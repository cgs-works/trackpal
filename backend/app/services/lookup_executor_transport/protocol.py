"""Transport port and common errors for lookup executor communication."""

from __future__ import annotations

from typing import Any, Protocol

from app.schemas.lookup_executor_protocol import (
    ChallengeResult,
    HandoffResult,
)


class TransportError(RuntimeError):
    """Raised when a challenge cannot produce a valid protocol response."""


class LookupExecutorTransport(Protocol):
    """Port used by the coordinator to communicate with an executor."""

    async def challenge(self, executor: Any, challenge: str) -> ChallengeResult:
        """Authenticate an executor and read its advertised capabilities."""
        ...

    async def handoff(self, executor: Any, envelope: Any) -> HandoffResult:
        """Send an encrypted execution envelope to an executor."""
        ...


__all__ = ["LookupExecutorTransport", "TransportError"]
