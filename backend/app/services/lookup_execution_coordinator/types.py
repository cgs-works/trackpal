"""Value types shared by lookup coordination store implementations."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True, slots=True)
class LookupLease:
    """An execution lease held by one external lookup executor."""

    job_id: UUID
    executor_id: UUID
    lease_id: UUID
    expires_at: datetime


LeaseRecord = LookupLease

__all__ = ["LeaseRecord", "LookupLease"]
