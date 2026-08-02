"""Gmail IMAP app-password provider."""

from __future__ import annotations

import asyncio
import email as email_lib
import imaplib
from collections.abc import Callable
from contextlib import suppress
from datetime import UTC, datetime, timedelta
from email.header import decode_header
from email.message import Message
from email.utils import getaddresses, parsedate_to_datetime
from typing import Any

from app.pipeline.email_message import EmailMessage

from .errors import NonTransientProviderError, TransientProviderError

GMAIL_IMAP_HOST = "imap.gmail.com"
GMAIL_IMAP_PORT = 993
IMAP_FETCH_TIMEOUT = 20.0
MAX_MESSAGES = 20
ImapFactory = Callable[[str, int], Any]


def _after_query(window_minutes: int, now: datetime) -> str:
    """Build Gmail's exact-instant search query."""
    current = now if now.tzinfo is not None else now.replace(tzinfo=UTC)
    seconds = int(
        (current.astimezone(UTC) - timedelta(minutes=window_minutes)).timestamp()
    )
    return f"after:{seconds}"


async def fetch_gmail_messages(
    mailbox_email: str,
    app_password: str,
    window_minutes: int,
    *,
    imap_factory: ImapFactory | None = None,
    now: datetime | None = None,
) -> list[EmailMessage]:
    """Fetch the newest messages in a recent Gmail window.

    The app password is accepted only for this invocation and is never placed
    in an email model or provider exception. IMAP is synchronous, so the
    complete connection lifecycle runs in a worker thread.
    """
    factory = imap_factory or imaplib.IMAP4_SSL
    current = now or datetime.now(UTC)

    try:
        return await asyncio.wait_for(
            asyncio.to_thread(
                _fetch_sync,
                mailbox_email,
                app_password,
                window_minutes,
                factory,
                current,
            ),
            timeout=IMAP_FETCH_TIMEOUT,
        )
    except TimeoutError as exc:
        raise TransientProviderError("IMAP fetch timed out") from exc


def _fetch_sync(
    mailbox_email: str,
    app_password: str,
    window_minutes: int,
    imap_factory: ImapFactory,
    now: datetime,
) -> list[EmailMessage]:
    try:
        connection = imap_factory(GMAIL_IMAP_HOST, GMAIL_IMAP_PORT)
    except Exception as exc:
        raise TransientProviderError("Could not connect to Gmail IMAP") from exc

    try:
        try:
            status, _ = connection.login(mailbox_email, app_password)
        except (imaplib.IMAP4.abort, TimeoutError, OSError, ConnectionError) as exc:
            raise TransientProviderError(
                "Gmail authentication service unavailable"
            ) from exc
        except imaplib.IMAP4.error as exc:
            if _is_authentication_rejection(exc):
                raise NonTransientProviderError("Gmail authentication failed") from exc
            raise TransientProviderError(
                "Gmail authentication failed temporarily"
            ) from exc
        except Exception as exc:
            raise TransientProviderError(
                "Gmail authentication service unavailable"
            ) from exc

        if status == "NO":
            raise NonTransientProviderError("Gmail authentication failed")
        if status != "OK":
            raise TransientProviderError("Gmail authentication failed temporarily")

        try:
            select_status, _ = connection.select("INBOX")
            if select_status != "OK":
                raise RuntimeError("INBOX selection failed")
            search_status, search_data = connection.search(
                None, "X-GM-RAW", f'"{_after_query(window_minutes, now)}"'
            )
            if search_status != "OK":
                raise RuntimeError("Gmail search failed")
            raw_ids = search_data[0] if search_data else b""
            message_ids = raw_ids.split() if raw_ids else []

            messages: list[EmailMessage] = []
            for message_id in message_ids[-MAX_MESSAGES:]:
                fetch_status, raw_data = connection.fetch(
                    message_id,
                    "(BODY.PEEK[])",
                )
                if fetch_status != "OK":
                    raise RuntimeError("Gmail message fetch failed")
                raw_message = _extract_raw_bytes(raw_data)
                if raw_message is None:
                    continue
                parsed = _parse_message(raw_message)
                if parsed is not None:
                    messages.append(parsed)
            return messages
        except NonTransientProviderError:
            raise
        except Exception as exc:
            raise TransientProviderError("Gmail search or fetch failed") from exc
    finally:
        with suppress(Exception):
            connection.logout()


def _is_authentication_rejection(error: imaplib.IMAP4.error) -> bool:
    """Recognize explicit credential failures without exposing their text."""
    message = str(error).lower()
    return any(
        marker in message
        for marker in (
            "auth",
            "credential",
            "password",
            "invalid user",
            "authentication",
        )
    )


def _extract_raw_bytes(raw_data: Any) -> bytes | None:
    """Extract the RFC 822 bytes from an IMAP fetch response."""
    if not raw_data:
        return None
    for item in raw_data:
        if isinstance(item, tuple) and len(item) > 1 and isinstance(item[1], bytes):
            return item[1]
    return None


def _parse_message(raw_message: bytes) -> EmailMessage | None:
    try:
        message = email_lib.message_from_bytes(raw_message)
    except (TypeError, ValueError):
        return None

    message_id = message.get("Message-ID", "").strip().strip("<>") or None
    return EmailMessage(
        subject=_decode_header(message.get("Subject", "")),
        body=_extract_body(message) or "",
        received_at=_parse_date(message.get("Date", "")),
        message_id=message_id,
        sender=message.get("From", "") or None,
        to_recipients=_extract_recipients(
            message.get("To", ""),
            message.get("Cc", ""),
        ),
    )


def _extract_body(message: Message) -> str | None:
    if message.is_multipart():
        for part in message.walk():
            if part.get_content_type() != "text/plain":
                continue
            decoded = part.get_payload(decode=True)
            if isinstance(decoded, bytes):
                return _decode_payload(decoded, part.get_content_charset())
        return None

    decoded = message.get_payload(decode=True)
    if isinstance(decoded, bytes):
        return _decode_payload(decoded, message.get_content_charset())
    return None


def _decode_payload(payload: bytes, charset: str | None) -> str:
    try:
        return payload.decode(charset or "utf-8", errors="replace")
    except LookupError:
        return payload.decode("utf-8", errors="replace")


def _decode_header(value: str) -> str:
    parts: list[str] = []
    for part, charset in decode_header(value):
        if isinstance(part, bytes):
            parts.append(_decode_payload(part, charset))
        else:
            parts.append(str(part))
    return " ".join(parts)


def _parse_date(value: str) -> datetime:
    try:
        parsed = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return datetime.now(UTC)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _extract_recipients(*headers: str) -> tuple[str, ...]:
    seen: set[str] = set()
    recipients: list[str] = []
    for _, address in getaddresses(headers):
        normalized = address.strip().lower()
        if normalized and normalized not in seen:
            seen.add(normalized)
            recipients.append(normalized)
    return tuple(recipients)


__all__ = [
    "GMAIL_IMAP_HOST",
    "GMAIL_IMAP_PORT",
    "fetch_gmail_messages",
]
