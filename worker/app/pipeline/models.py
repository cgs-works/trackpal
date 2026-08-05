"""Pydantic contracts for standalone lookup execution."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

OutcomeKind = Literal["found", "not_found", "retryable_failure", "terminal_failure"]
ResultType = Literal["code", "url"]


class LookupExclusion(BaseModel):
    """One previously delivered result that must not end a new lookup."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    message_id: str | None = None
    fingerprint: str


class LookupCommand(BaseModel):
    """Decrypted, in-memory inputs for one mailbox lookup."""

    model_config = ConfigDict(extra="forbid")

    mailbox_email: str
    app_password: str
    service_key: str
    target_email: str
    window_minutes: int = Field(default=5, gt=0)
    search_after: datetime | None = None
    timeout_seconds: int = Field(default=55, gt=0)
    deadline_at: datetime | None = None
    excluded_deliveries: list[LookupExclusion] = Field(default_factory=list)
    job_id: UUID | None = None
    lease_id: UUID | None = None
    callback_url: str | None = None
    lease_expires_at: datetime | None = None


class LookupOutcome(BaseModel):
    """Safe callback result containing no mailbox secret or raw email content."""

    model_config = ConfigDict(extra="forbid")

    kind: OutcomeKind
    result_type: ResultType | None = None
    result_value: str | None = None
    message_id: str | None = None
    fingerprint: str | None = None
    error_code: str | None = None
    error_detail: str | None = None

    @classmethod
    def found(
        cls,
        result_type: ResultType,
        result_value: str,
        message_id: str | None,
        fingerprint: str,
    ) -> LookupOutcome:
        """Build a successful normalized result."""
        return cls(
            kind="found",
            result_type=result_type,
            result_value=result_value,
            message_id=message_id,
            fingerprint=fingerprint,
        )

    @classmethod
    def not_found(cls) -> LookupOutcome:
        """Build a valid lookup with no matching result."""
        return cls(kind="not_found")

    @classmethod
    def retryable(cls, error_code: str, error_detail: str) -> LookupOutcome:
        """Build a safe retryable failure."""
        return cls(
            kind="retryable_failure",
            error_code=error_code,
            error_detail=error_detail,
        )

    @classmethod
    def terminal(cls, error_code: str, error_detail: str) -> LookupOutcome:
        """Build a safe terminal failure."""
        return cls(
            kind="terminal_failure",
            error_code=error_code,
            error_detail=error_detail,
        )


__all__ = [
    "LookupCommand",
    "LookupExclusion",
    "LookupOutcome",
    "OutcomeKind",
    "ResultType",
]
