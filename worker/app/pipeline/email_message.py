"""Normalized email representation for the worker pipeline."""

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class EmailMessage:
    """Provider-independent email message data."""

    subject: str
    body: str
    received_at: datetime
    message_id: str | None = None
    sender: str | None = None
    to_recipients: tuple[str, ...] = ()
