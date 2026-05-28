"""Google Gmail API email fetch adapter."""

from __future__ import annotations

import base64
import logging

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
    _extract_email_addresses,
    _parse_email_date,
)

logger = logging.getLogger(__name__)

GMAIL_API_BASE = "https://gmail.googleapis.com/gmail/v1/users/me"


async def fetch_google_emails(
    mailbox: TenantMailbox,
    window_minutes: int,
    db: AsyncSession | None = None,
) -> list[EmailMessage]:
    """Fetch recent Gmail messages via the Gmail API.

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
    q = f"after:{int(since_dt.timestamp())}"

    attempt = 0
    while True:
        headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}

        async with httpx.AsyncClient(timeout=DEFAULT_FETCH_TIMEOUT) as client:
            resp = await client.get(
                f"{GMAIL_API_BASE}/messages",
                params={"q": q, "maxResults": 20},
                headers=headers,
            )

            if resp.status_code == 401 and attempt == 0 and db is not None:
                # Token expired — attempt refresh
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
                continue  # Retry with new token

            if resp.status_code == 401:
                raise NonTransientProviderError("Gmail token expired/revoked")
            if resp.status_code == 403:
                raise NonTransientProviderError(
                    "Gmail API access denied", error_code="permission_denied"
                )
            if resp.status_code == 429:
                raise TransientProviderError("Gmail rate limit exceeded")
            resp.raise_for_status()

            data = resp.json()
            message_list = data.get("messages", [])
            if not message_list:
                return []

            emails: list[EmailMessage] = []
            for msg_ref in message_list:
                msg_id = msg_ref["id"]
                msg_resp = await client.get(
                    f"{GMAIL_API_BASE}/messages/{msg_id}",
                    params={"format": "full"},
                    headers=headers,
                )
                if msg_resp.status_code != 200:
                    logger.warning(
                        "Gmail: skipping message %s (HTTP %d)",
                        msg_id,
                        msg_resp.status_code,
                    )
                    continue

                email = _parse_gmail_message(msg_id, msg_resp.json())
                if email is not None:
                    emails.append(email)

            return emails


def _parse_gmail_message(msg_id: str, data: dict) -> EmailMessage | None:
    """Parse a Gmail API message resource into EmailMessage."""
    payload = data.get("payload", {})
    headers_map = {h["name"].lower(): h["value"] for h in payload.get("headers", [])}

    subject = headers_map.get("subject", "")
    message_id = headers_map.get("message-id", msg_id)
    sender = headers_map.get("from", "")
    received_str = headers_map.get("date", "")
    received_at = _parse_email_date(received_str)

    body = _extract_gmail_body(payload)
    if body is None:
        return None

    to_header = headers_map.get("to", "")
    cc_header = headers_map.get("cc", "")
    recipients = _extract_email_addresses(to_header, cc_header)

    return EmailMessage(
        subject=subject,
        body=body,
        received_at=received_at,
        message_id=message_id,
        sender=sender,
        to_recipients=recipients,
    )


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


def _extract_gmail_body(payload: dict) -> str | None:
    """Recursively extract plain text body from Gmail message payload."""
    if payload.get("mimeType") == "text/plain":
        body_data = payload.get("body", {}).get("data", "")
        if body_data:
            try:
                decoded = base64.urlsafe_b64decode(body_data).decode(
                    "utf-8", errors="replace"
                )
                return decoded
            except Exception:
                return body_data
        return ""

    parts = payload.get("parts", [])
    for part in parts:
        result = _extract_gmail_body(part)
        if result:
            return result

    return ""
