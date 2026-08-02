"""Protocol v1 value objects shared by the backend transport adapters."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
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
