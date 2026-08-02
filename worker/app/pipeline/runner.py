"""Orchestration for one standalone mailbox lookup."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Protocol

from app.extractors import extract_newest_with_source
from app.pipeline.email_message import EmailMessage
from app.pipeline.fingerprint import compute_fingerprint
from app.providers.errors import NonTransientProviderError, ProviderFetchError

from .models import LookupCommand, LookupOutcome

MAX_FETCH_ATTEMPTS = 3
BASE_RETRY_DELAY_SECONDS = 1.0


class MailProviderPort(Protocol):
    """Provider port required by the runner."""

    async def fetch(self, command: LookupCommand) -> list[EmailMessage]:
        """Fetch normalized messages for a command."""


class NetflixResolverPort(Protocol):
    """Netflix URL resolution port required by the runner."""

    async def resolve(self, full_url: str) -> str | None:
        """Resolve a travel verification URL to an OTP."""


def safe_provider_detail(error_code: str) -> str:
    """Return a stable detail that cannot expose provider exception text."""
    details = {
        "auth_failed": "Authentication failed — check mailbox credentials",
        "provider_config_error": "Mailbox configuration error — check settings",
    }
    return details.get(error_code, "Provider error — check mailbox configuration")


async def execute_lookup(
    command: LookupCommand,
    provider: MailProviderPort,
    netflix: NetflixResolverPort,
    *,
    now: datetime | None = None,
) -> LookupOutcome:
    """Fetch, extract, resolve, and fingerprint one lookup."""
    try:
        emails = await _fetch_with_retry(command, provider)
    except NonTransientProviderError as exc:
        return LookupOutcome.terminal(
            exc.error_code,
            safe_provider_detail(exc.error_code),
        )

    if emails is None:
        return LookupOutcome.retryable(
            "fetch_failed",
            "Email fetch failed after retries",
        )

    filtered = _filter_target_emails(emails, command.target_email)
    extraction_now = now or datetime.now(UTC)
    extracted = extract_newest_with_source(
        [
            {
                "subject": message.subject,
                "body": message.body,
                "received_at": message.received_at,
            }
            for message in filtered
        ],
        command.service_key,
        max_age_minutes=command.window_minutes,
        now=extraction_now,
    )
    if extracted is None:
        return LookupOutcome.not_found()

    result_value = extracted.result.value
    result_type = extracted.result.result_type
    if command.service_key == "netflix" and result_type == "url":
        result_value = await netflix.resolve(result_value) or ""
        if not result_value:
            return LookupOutcome.not_found()
        result_type = "code"

    match = filtered[extracted.source_index]
    fingerprint = compute_fingerprint(
        service_key=command.service_key,
        message_id=match.message_id,
        sender=match.sender,
        received_at_iso=match.received_at.isoformat(),
        subject=match.subject,
        payload_normalized=result_value,
    )
    return LookupOutcome.found(
        result_type=result_type,
        result_value=result_value,
        message_id=match.message_id,
        fingerprint=fingerprint,
    )


async def _fetch_with_retry(
    command: LookupCommand,
    provider: MailProviderPort,
) -> list[EmailMessage] | None:
    for attempt in range(MAX_FETCH_ATTEMPTS):
        failed = False
        try:
            return await provider.fetch(command)
        except NonTransientProviderError:
            raise
        except ProviderFetchError:
            failed = True
        except Exception:  # noqa: BLE001 - external provider boundary is fail-safe
            failed = True
        if failed and attempt < MAX_FETCH_ATTEMPTS - 1:
            await asyncio.sleep(BASE_RETRY_DELAY_SECONDS * (2**attempt))
    return None


def _filter_target_emails(
    emails: list[EmailMessage],
    target_email: str,
) -> list[EmailMessage]:
    target = target_email.strip().lower()
    return [
        email
        for email in emails
        if target in email.subject.lower()
        or target in email.body.lower()
        or target in {recipient.lower() for recipient in email.to_recipients}
    ]


__all__ = [
    "BASE_RETRY_DELAY_SECONDS",
    "MAX_FETCH_ATTEMPTS",
    "execute_lookup",
    "safe_provider_detail",
]
