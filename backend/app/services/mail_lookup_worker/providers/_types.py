"""Shared types for provider fetch adapters."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

logger = logging.getLogger(__name__)

DEFAULT_FETCH_TIMEOUT = 15
IMAP_FETCH_TIMEOUT = 20


class EmailMessage:
    """Normalised email message for the extraction pipeline."""

    __slots__ = (
        "subject",
        "body",
        "received_at",
        "message_id",
        "sender",
        "to_recipients",
    )

    def __init__(
        self,
        subject: str,
        body: str,
        received_at: datetime,
        message_id: str | None = None,
        sender: str | None = None,
        to_recipients: list[str] | None = None,
    ) -> None:
        self.subject = subject
        self.body = body
        self.received_at = received_at
        self.message_id = message_id
        self.sender = sender
        self.to_recipients = to_recipients if to_recipients is not None else []

    def __repr__(self) -> str:
        return (
            f"EmailMessage(subject={self.subject!r}, "
            f"message_id={self.message_id!r}, sender={self.sender!r}, "
            f"to_recipients={self.to_recipients!r})"
        )


class ProviderFetchError(Exception):
    """Base for all provider fetch errors."""


class TransientProviderError(ProviderFetchError):
    """Network, rate-limit, timeout — safe to retry."""


class NonTransientProviderError(ProviderFetchError):
    """Auth failure, revoked, insufficient permissions — do NOT retry.

    ``error_code`` classifies the failure for safe job status recording:
    - ``auth_failed`` — token/password expired, invalid, or decryption failed
    - ``provider_config_error`` — missing host, unsupported provider, no token stored
    - ``permission_denied`` — API 403, scope insufficient
    - ``mailbox_revoked`` — OAuth invalid_grant (subclass RevokedMailboxError)
    """

    def __init__(self, message: str, error_code: str = "auth_failed") -> None:
        super().__init__(message)
        self.error_code = error_code


class RevokedMailboxError(NonTransientProviderError):
    """Mailbox was revoked due to invalid_grant — explicit revoked signal."""

    def __init__(self, message: str = "") -> None:
        super().__init__(message, error_code="mailbox_revoked")


def _parse_email_date(date_str: str) -> datetime:
    """Parse RFC 2822 or similar date string to datetime (UTC)."""
    try:
        dt = parsedate_to_datetime(date_str)
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt
    except (ValueError, TypeError):
        return datetime.now(timezone.utc)


def _extract_email_addresses(*header_values: str) -> list[str]:
    """Extract email addresses from RFC 2822 To/Cc header values.

    Handles formats like:
      - "User <user@example.com>"
      - "user@example.com"
      - "User1 <a@a.com>, User2 <b@b.com>"
    Returns lowercased, deduplicated emails in order of appearance.
    """
    from email.utils import getaddresses

    seen: set[str] = set()
    result: list[str] = []
    for header in header_values:
        if not header:
            continue
        for _, addr in getaddresses([header]):
            addr = addr.strip().lower()
            if addr and addr not in seen:
                seen.add(addr)
                result.append(addr)
    return result
