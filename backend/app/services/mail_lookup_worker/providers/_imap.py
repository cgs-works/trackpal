"""IMAP email fetch adapter with app-password auth."""

from __future__ import annotations

import asyncio
import email as email_lib
import imaplib
import logging
from contextlib import suppress
from datetime import datetime, timedelta, timezone
from email.header import decode_header
from email.message import Message
from typing import Any

from app.core.encryption import decrypt_value
from app.models.tenant_mailbox import TenantMailbox
from app.services.mail_lookup_worker.providers._types import (
    IMAP_FETCH_TIMEOUT,
    EmailMessage,
    NonTransientProviderError,
    TransientProviderError,
    _extract_email_addresses,
    _parse_email_date,
)

logger = logging.getLogger(__name__)


async def fetch_imap_emails(
    mailbox: TenantMailbox,
    window_minutes: int,
) -> list[EmailMessage]:
    """Fetch recent emails via IMAP with app-password auth."""
    host = mailbox.imap_host
    if not host:
        raise NonTransientProviderError(
            "IMAP host not configured", error_code="provider_config_error"
        )
    port = mailbox.imap_port or 993
    ssl = mailbox.imap_ssl if mailbox.imap_ssl is not None else True
    username = mailbox.mailbox_email
    password = _get_imap_password(mailbox)

    since_str = _build_since_query(window_minutes)

    loop = asyncio.get_running_loop()

    def _sync_fetch() -> list[EmailMessage]:
        imap_host: str = host
        try:
            if ssl:
                conn = imaplib.IMAP4_SSL(imap_host, port)
            else:
                conn = imaplib.IMAP4(imap_host, port)
        except Exception as exc:
            raise TransientProviderError(
                f"Cannot connect to {host}:{port}: {exc}"
            ) from exc

        try:
            result = conn.login(username, password)
            if result[0] != "OK":
                raise NonTransientProviderError(
                    f"IMAP auth failed: {result[1].decode('utf-8', errors='replace')}"
                )
        except NonTransientProviderError:
            raise
        except Exception as exc:
            raise NonTransientProviderError(f"IMAP login failed: {exc}") from exc

        try:
            conn.select("INBOX")
            _, search_data = conn.search(None, f"SINCE {since_str}")
            msg_ids = search_data[0].split() if search_data[0] else []

            emails: list[EmailMessage] = []
            for bid in msg_ids[-20:]:
                _, raw_data = conn.fetch(bid, "(BODY.PEEK[])")
                raw_email = _extract_raw_bytes(raw_data)
                if raw_email is None:
                    continue

                parsed = _parse_imap_message(raw_email)
                if parsed is not None:
                    emails.append(parsed)

            return emails

        except Exception as exc:
            raise TransientProviderError(f"IMAP search/fetch failed: {exc}") from exc
        finally:
            with suppress(Exception):
                conn.logout()

    try:
        return await asyncio.wait_for(
            loop.run_in_executor(None, _sync_fetch),
            timeout=IMAP_FETCH_TIMEOUT,
        )
    except asyncio.TimeoutError as exc:
        raise TransientProviderError(
            f"IMAP fetch timed out after {IMAP_FETCH_TIMEOUT}s"
        ) from exc


def _get_imap_password(mailbox: TenantMailbox) -> str:
    """Decrypt and return IMAP password, or raise NonTransient."""
    encrypted = mailbox.imap_password_encrypted
    if not encrypted:
        raise NonTransientProviderError(
            "No IMAP password stored", error_code="provider_config_error"
        )
    password = decrypt_value(encrypted)
    if password is None:
        raise NonTransientProviderError("Failed to decrypt IMAP password")
    return password


def _build_since_query(window_minutes: int) -> str:
    """Build an RFC 3501 SINCE date string."""
    since = datetime.now(timezone.utc) - timedelta(minutes=window_minutes)
    return since.strftime("%d-%b-%Y")


def _extract_raw_bytes(raw_data: Any) -> bytes | None:
    """Extract raw email bytes from IMAP fetch response."""
    if raw_data is not None and len(raw_data) > 0:
        item = raw_data[0]
        if isinstance(item, tuple) and len(item) > 1:
            val = item[1]
            if isinstance(val, bytes):
                return val
    return None


def _parse_imap_message(raw_bytes: bytes) -> EmailMessage | None:
    """Parse raw IMAP message bytes into EmailMessage."""
    try:
        msg = email_lib.message_from_bytes(raw_bytes)
    except Exception:
        return None

    subject = _decode_mime_header(msg.get("Subject", ""))
    message_id = msg.get("Message-ID", "").strip("<>")
    sender = msg.get("From", "")
    received_at = _parse_email_date(msg.get("Date", ""))

    body = _extract_body_payload(msg) or ""

    to_header = msg.get("To", "")
    cc_header = msg.get("Cc", "")
    recipients = _extract_email_addresses(to_header, cc_header)

    return EmailMessage(
        subject=subject,
        body=body,
        received_at=received_at,
        message_id=message_id or None,
        sender=sender,
        to_recipients=recipients,
    )


def _extract_body_payload(msg: Message) -> str | None:
    """Extract plain text body from an email.message.Message."""
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain":
                raw = part.get_payload(decode=True)
                if raw is not None and isinstance(raw, bytes):
                    charset = part.get_content_charset() or "utf-8"
                    try:
                        return raw.decode(charset, errors="replace")
                    except (LookupError, UnicodeDecodeError):
                        return raw.decode("utf-8", errors="replace")
        return None
    raw = msg.get_payload(decode=True)
    if raw is not None and isinstance(raw, bytes):
        charset = msg.get_content_charset() or "utf-8"
        try:
            return raw.decode(charset, errors="replace")
        except (LookupError, UnicodeDecodeError):
            return raw.decode("utf-8", errors="replace")
    return None


def _decode_mime_header(header: str) -> str:
    """Decode RFC 2047 encoded header values."""
    decoded_parts = decode_header(header)
    result = []
    for part, charset in decoded_parts:
        if isinstance(part, bytes):
            try:
                result.append(part.decode(charset or "utf-8", errors="replace"))
            except (LookupError, UnicodeDecodeError):
                result.append(part.decode("utf-8", errors="replace"))
        else:
            result.append(str(part))
    return " ".join(result)
