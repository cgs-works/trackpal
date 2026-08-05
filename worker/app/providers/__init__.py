"""Mail provider interfaces and Gmail implementation."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from app.pipeline.email_message import EmailMessage

from .errors import (
    NonTransientProviderError,
    ProviderFetchError,
    TransientProviderError,
)
from .gmail_imap import fetch_gmail_messages

if TYPE_CHECKING:
    from app.pipeline.models import LookupCommand


class MailProvider(Protocol):
    """Provider port consumed by the lookup runner."""

    async def fetch(self, command: LookupCommand) -> list[EmailMessage]:
        """Fetch messages for a lookup command."""


class GmailImapProvider:
    """MailProvider adapter backed by Gmail IMAP."""

    async def fetch(self, command: LookupCommand) -> list[EmailMessage]:
        """Fetch messages using credentials from the current command only."""
        return await fetch_gmail_messages(
            command.mailbox_email,
            command.app_password,
            command.window_minutes,
            search_after=command.search_after,
        )


__all__ = [
    "EmailMessage",
    "GmailImapProvider",
    "MailProvider",
    "NonTransientProviderError",
    "ProviderFetchError",
    "TransientProviderError",
    "fetch_gmail_messages",
]
