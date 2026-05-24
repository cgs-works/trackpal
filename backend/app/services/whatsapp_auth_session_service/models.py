"""Domain models for WhatsApp auth session + lockout."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from pydantic import BaseModel


class WhatsAppAuthSession(BaseModel):
    """Authenticated session keyed by phone.

    Created *after* username+password verification succeeds.
    """

    phone: str
    user_id: UUID
    username: str
    role: str
    authenticated_at: datetime


class WhatsAppAuthFailState(BaseModel):
    """Consecutive failure counter with timestamps."""

    count: int
    first_failed_at: datetime
    last_failed_at: datetime


class WhatsAppAuthLockState(BaseModel):
    """Temporary lockout marker."""

    locked_until: datetime

    @property
    def is_locked(self) -> bool:
        """``True`` when the lock window has not yet expired."""
        return self.locked_until > datetime.now(timezone.utc)
