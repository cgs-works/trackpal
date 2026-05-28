"""Microsoft Graph API email fetch adapter."""

from __future__ import annotations

import logging
import re
from datetime import datetime

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.encryption import decrypt_value
from app.models.tenant_mailbox import TenantMailbox
from app.services.mail_lookup_worker.providers._types import (
    DEFAULT_FETCH_TIMEOUT,
    EmailMessage,
    NonTransientProviderError,
    RevokedMailboxError,
    TransientProviderError,
)

logger = logging.getLogger(__name__)

GRAPH_API_BASE = "https://graph.microsoft.com/v1.0/me/messages"


async def fetch_microsoft_emails(
    mailbox: TenantMailbox,
    window_minutes: int,
    db: AsyncSession | None = None,
) -> list[EmailMessage]:
    """Fetch recent Outlook messages via Microsoft Graph.

    Handles token refresh on 401: if ``db`` is provided and the access
    token has expired, attempts a refresh via ``MailboxOAuthService``.
    """
    encrypted = mailbox.oauth_access_token_encrypted
    if not encrypted:
        raise NonTransientProviderError(
            "No OAuth access token stored", error_code="provider_config_error"
        )
    token = decrypt_value(encrypted)
    if token is None:
        raise NonTransientProviderError("Failed to decrypt OAuth access token")

    from datetime import datetime, timedelta, timezone

    since_dt = datetime.now(timezone.utc) - timedelta(minutes=window_minutes)
    filter_str = f"receivedDateTime ge {since_dt.isoformat()}"

    attempt = 0
    while True:
        headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}

        async with httpx.AsyncClient(timeout=DEFAULT_FETCH_TIMEOUT) as client:
            resp = await client.get(
                GRAPH_API_BASE,
                params={
                    "$filter": filter_str,
                    "$top": 20,
                    "$orderby": "receivedDateTime DESC",
                    "$select": "id,subject,body,from,receivedDateTime,internetMessageId,toRecipients,ccRecipients",
                },
                headers=headers,
            )

            if resp.status_code == 401 and attempt == 0 and db is not None:
                await _maybe_refresh_oauth(db, mailbox)
                encrypted = mailbox.oauth_access_token_encrypted
                if not encrypted:
                    raise NonTransientProviderError(
                        "No OAuth token available after refresh",
                        error_code="provider_config_error",
                    )
                token = decrypt_value(encrypted)
                if token is None:
                    raise NonTransientProviderError(
                        "Failed to decrypt refreshed OAuth token"
                    )
                attempt = 1
                continue

            if resp.status_code == 401:
                raise NonTransientProviderError("Microsoft token expired/revoked")
            if resp.status_code == 403:
                raise NonTransientProviderError(
                    "Microsoft Graph access denied", error_code="permission_denied"
                )
            if resp.status_code == 429:
                raise TransientProviderError("Microsoft Graph rate limit exceeded")
            resp.raise_for_status()

            data = resp.json()
            messages = data.get("value", [])
            if not messages:
                return []

            emails: list[EmailMessage] = []
            for msg in messages:
                email = _parse_graph_message(msg)
                if email is not None:
                    emails.append(email)

            return emails


def _parse_graph_message(msg: dict) -> EmailMessage | None:
    """Parse a Microsoft Graph message resource into EmailMessage."""
    subject = msg.get("subject", "")
    message_id = msg.get("internetMessageId") or msg.get("id", "")
    sender_data = msg.get("from", {}).get("emailAddress", {})
    sender = sender_data.get("address", "")
    received_str = msg.get("receivedDateTime", "")
    received_at = _parse_graph_datetime(received_str)

    body_content = msg.get("body", {}).get("content", "")
    body_type = msg.get("body", {}).get("contentType", "")
    if body_type == "html":
        body_content = re.sub(r"<[^>]+>", " ", body_content).strip()

    recipients = _extract_graph_recipients(msg)

    return EmailMessage(
        subject=subject,
        body=body_content,
        received_at=received_at,
        message_id=message_id,
        sender=sender,
        to_recipients=recipients,
    )


def _extract_graph_recipients(msg: dict) -> list[str]:
    """Extract recipient email addresses from Microsoft Graph message."""
    to_addrs: list[str] = []
    for entry in msg.get("toRecipients", []):
        addr = entry.get("emailAddress", {}).get("address", "")
        if addr:
            to_addrs.append(addr)
    for entry in msg.get("ccRecipients", []):
        addr = entry.get("emailAddress", {}).get("address", "")
        if addr:
            to_addrs.append(addr)
    seen: set[str] = set()
    result: list[str] = []
    for a in to_addrs:
        a_lower = a.strip().lower()
        if a_lower and a_lower not in seen:
            seen.add(a_lower)
            result.append(a_lower)
    return result


async def _maybe_refresh_oauth(db: AsyncSession, mailbox: TenantMailbox) -> None:
    """Attempt OAuth token refresh.

    On ``invalid_grant``: marks mailbox ``revoked`` and raises
    ``RevokedMailboxError``.
    """
    from app.services.oauth_service import MailboxOAuthService

    oauth = MailboxOAuthService()
    refreshed = await oauth.refresh_token(db, mailbox)
    if refreshed is None:
        raise NonTransientProviderError(
            "OAuth refresh not available for this mailbox",
            error_code="provider_config_error",
        )
    if refreshed.status == "revoked":
        raise RevokedMailboxError(
            "OAuth token revoked — mailbox marked revoked, reconnection required"
        )


def _parse_graph_datetime(date_str: str) -> datetime:
    """Parse ISO 8601 datetime string from Graph API."""
    from datetime import timezone

    try:
        dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        return dt
    except (ValueError, TypeError):
        return datetime.now(timezone.utc)
