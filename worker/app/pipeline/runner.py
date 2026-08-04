"""Orchestration for one standalone mailbox lookup."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from time import monotonic
from typing import Protocol

from app.extractors import extract_newest_with_source
from app.pipeline.email_message import EmailMessage
from app.pipeline.fingerprint import compute_fingerprint
from app.providers.errors import NonTransientProviderError

from .models import LookupCommand, LookupOutcome

MAX_FETCH_ATTEMPTS = 3
BASE_RETRY_DELAY_SECONDS = 1.0
POLL_INTERVAL_SECONDS = 4.0


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
    deadline = monotonic() + command.timeout_seconds
    extraction_now = now or datetime.now(UTC)
    excluded_deliveries = {
        (entry.message_id, entry.fingerprint) for entry in command.excluded_deliveries
    }

    while True:
        remaining = deadline - monotonic()
        if remaining <= 0:
            return LookupOutcome.not_found()

        try:
            emails = await asyncio.wait_for(
                _fetch_with_retry(command, provider), timeout=remaining
            )
        except TimeoutError:
            return LookupOutcome.retryable(
                "fetch_timeout",
                "Email fetch timed out before the lookup deadline",
            )
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

        candidates = _filter_target_emails(emails, command.target_email)
        while candidates:
            extracted = extract_newest_with_source(
                [
                    {
                        "subject": message.subject,
                        "body": message.body,
                        "received_at": message.received_at,
                    }
                    for message in candidates
                ],
                command.service_key,
                max_age_minutes=command.window_minutes,
                now=extraction_now,
            )
            if extracted is None:
                break

            result_value = extracted.result.value
            result_type = extracted.result.result_type
            match = candidates[extracted.source_index]
            if command.service_key == "netflix" and result_type == "url":
                result_value = await netflix.resolve(result_value) or ""
                if not result_value:
                    candidates.pop(extracted.source_index)
                    continue
                result_type = "code"

            fingerprint = compute_fingerprint(
                service_key=command.service_key,
                message_id=match.message_id,
                sender=match.sender,
                received_at_iso=match.received_at.isoformat(),
                subject=match.subject,
                payload_normalized=result_value,
            )
            if (match.message_id, fingerprint) in excluded_deliveries:
                candidates.pop(extracted.source_index)
                continue

            return LookupOutcome.found(
                result_type=result_type,
                result_value=result_value,
                message_id=match.message_id,
                fingerprint=fingerprint,
            )

        remaining = deadline - monotonic()
        if remaining <= 0:
            return LookupOutcome.not_found()
        await asyncio.sleep(min(POLL_INTERVAL_SECONDS, remaining))


async def _fetch_with_retry(
    command: LookupCommand,
    provider: MailProviderPort,
) -> list[EmailMessage] | None:
    for attempt in range(MAX_FETCH_ATTEMPTS):
        try:
            return await provider.fetch(command)
        except NonTransientProviderError:
            raise
        except Exception:  # noqa: BLE001 - external provider boundary is fail-safe
            if attempt == MAX_FETCH_ATTEMPTS - 1:
                return None
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
    "POLL_INTERVAL_SECONDS",
    "execute_lookup",
    "safe_provider_detail",
]
