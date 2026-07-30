"""Gmail app-password validation module."""

from __future__ import annotations

from typing import Final, Literal

from app.services.imap_service import (
    ImapAuthenticationError,
    ImapTimeoutError,
    ImapUnavailableError,
    test_imap_connection,
)

GMAIL_IMAP_HOST: Final = "imap.gmail.com"
GMAIL_IMAP_PORT: Final = 993
GMAIL_IMAP_SSL: Final = True


class GmailAppPasswordError(Exception):
    """Safe error raised when Gmail app-password validation fails."""

    def __init__(
        self,
        code: Literal["authentication_rejected", "timeout", "unavailable"],
    ) -> None:
        self.code = code
        super().__init__(code)


def normalize_app_password(raw: str) -> str:
    """Strip whitespace and remove grouping spaces from an app password."""
    return "".join(raw.strip().split())


async def validate_gmail_app_password(
    mailbox_email: str,
    raw_password: str,
) -> str:
    """Validate a Gmail app password by testing IMAP connection.

    Returns the normalized credential on success.
    Raises ``GmailAppPasswordError`` with a safe error code on failure.
    """
    normalized = normalize_app_password(raw_password)
    if not normalized:
        raise GmailAppPasswordError("authentication_rejected")
    try:
        await test_imap_connection(
            host=GMAIL_IMAP_HOST,
            port=GMAIL_IMAP_PORT,
            ssl=GMAIL_IMAP_SSL,
            username=mailbox_email,
            password=normalized,
        )
    except ImapAuthenticationError as exc:
        raise GmailAppPasswordError("authentication_rejected") from exc
    except ImapTimeoutError as exc:
        raise GmailAppPasswordError("timeout") from exc
    except ImapUnavailableError as exc:
        raise GmailAppPasswordError("unavailable") from exc
    return normalized
