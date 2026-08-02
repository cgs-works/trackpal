"""Protocol v1 value objects shared by the backend transport adapters."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


@dataclass(frozen=True)
class ProtocolKeys:
    """Independent signing and encryption keys derived from one secret."""

    signing: bytes
    encryption: bytes


class EncryptedBody(BaseModel):
    """Base64-encoded AES-GCM payload components."""

    model_config = ConfigDict(extra="forbid")

    nonce: str
    ciphertext: str


@dataclass(frozen=True)
class ChallengeResult:
    """Capabilities returned by an executor after a successful challenge."""

    executor_id: UUID
    protocol_version: int
    runtime_version: str
    max_concurrency: int


class HandoffStatus(str, Enum):
    """Stable outcomes returned by an executor handoff attempt."""

    ACCEPTED = "accepted"
    DUPLICATE_SAME_LEASE = "duplicate_same_lease"
    BUSY = "busy"
    SECURITY_ERROR = "security_error"
    PROTOCOL_ERROR = "protocol_error"
    TRANSPORT_ERROR = "transport_error"


@dataclass(frozen=True)
class HandoffResult:
    """Safe, normalized result of sending a command to an executor."""

    status: HandoffStatus
    lease_id: UUID | None = None
    safe_error: str | None = None


class ChallengePayload(BaseModel):
    """Encrypted challenge request payload."""

    challenge: str = Field(min_length=1)


OutcomeKind = Literal["found", "not_found", "retryable_failure", "terminal_failure"]
ResultType = Literal["code", "url"]


class LookupCallbackOutcome(BaseModel):
    """Safe executor outcome accepted by the callback boundary."""

    model_config = ConfigDict(extra="forbid")

    kind: OutcomeKind
    result_type: ResultType | None = None
    result_value: str | None = None
    message_id: str | None = None
    fingerprint: str | None = None
    error_code: str | None = None
    error_detail: str | None = None


class LookupCallbackEnvelope(BaseModel):
    """Decrypted callback body carrying job and lease identity."""

    model_config = ConfigDict(extra="forbid")

    job_id: UUID
    lease_id: UUID
    outcome: LookupCallbackOutcome


__all__ = [
    "ChallengePayload",
    "ChallengeResult",
    "EncryptedBody",
    "HandoffResult",
    "HandoffStatus",
    "LookupCallbackEnvelope",
    "LookupCallbackOutcome",
    "ProtocolKeys",
]
