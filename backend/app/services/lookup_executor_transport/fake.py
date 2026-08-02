"""In-memory transport used by backend coordination tests."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from app.schemas.lookup_executor_protocol import (
    ChallengeResult,
    HandoffResult,
    HandoffStatus,
)


class FakeLookupExecutorTransport:
    """Deterministic transport that accepts envelopes without network I/O."""

    def __init__(
        self,
        challenge_result: ChallengeResult | None = None,
        handoff_result: HandoffResult | None = None,
    ) -> None:
        self.challenge_result = challenge_result
        self.handoff_result = handoff_result
        self.challenges: list[str] = []
        self.envelopes: list[Any] = []

    async def challenge(self, executor: Any, challenge: str) -> ChallengeResult:
        """Record a challenge and return configured or default capabilities."""

        self.challenges.append(challenge)
        if self.challenge_result is not None:
            return self.challenge_result
        return ChallengeResult(
            executor_id=UUID(str(executor.id)),
            protocol_version=1,
            runtime_version="fake",
            max_concurrency=int(executor.max_concurrency),
        )

    async def handoff(self, executor: Any, envelope: Any) -> HandoffResult:
        """Record an envelope and return configured or accepted status."""

        self.envelopes.append(envelope)
        if self.handoff_result is not None:
            return self.handoff_result
        value = (
            envelope.get("lease_id")
            if isinstance(envelope, dict)
            else getattr(envelope, "lease_id", None)
        )
        lease_id = UUID(str(value)) if value is not None else None
        return HandoffResult(status=HandoffStatus.ACCEPTED, lease_id=lease_id)


__all__ = ["FakeLookupExecutorTransport"]
