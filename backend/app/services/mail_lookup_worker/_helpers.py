"""Internal helpers for the lookup job worker — not public API."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import MailLookupJob, TenantMailbox
from app.repositories import mailbox_dedupe_repository
from app.repositories import mailbox_lookup_repository
from app.services.mail_code_extractor import (
    ExtractedCode,
    ParsedEmail,
    extract_newest_from_emails,
)
from app.services.mail_lookup_worker.ephemeral_cache import store_result
from app.services.mail_lookup_worker.fingerprint import compute_fingerprint
from app.services.mail_lookup_worker.providers import (
    EmailMessage,
    NonTransientProviderError,
    ProviderFetchError,
    TransientProviderError,
    fetch_recent_emails,
)

logger = logging.getLogger(__name__)

_MAX_RETRIES = 3
_BASE_DELAY_S = 1.0


def resolve_provider_label(job: MailLookupJob) -> str:
    """Derive a provider label from the job for metrics."""
    try:
        if job.mailbox is not None:
            return "gmail"
    except Exception:
        pass
    return "unknown"


async def fetch_with_retry(
    mailbox: TenantMailbox,
    window_minutes: int,
) -> list[EmailMessage] | None:
    """Fetch emails with exponential backoff for transient errors.

    Returns ``None`` when all retries exhausted.
    """
    for attempt in range(_MAX_RETRIES):
        try:
            return await fetch_recent_emails(mailbox, window_minutes)
        except NonTransientProviderError:
            raise
        except NotImplementedError:
            raise
        except (TransientProviderError, ProviderFetchError) as exc:
            logger.warning(
                "Transient fetch error (attempt %d/%d): %s",
                attempt + 1,
                _MAX_RETRIES,
                exc,
            )
            if attempt < _MAX_RETRIES - 1:
                await asyncio.sleep(_BASE_DELAY_S * (2**attempt))
        except Exception as exc:
            logger.exception(
                "Unexpected fetch error (attempt %d/%d): %s",
                attempt + 1,
                _MAX_RETRIES,
                exc,
            )
            if attempt < _MAX_RETRIES - 1:
                await asyncio.sleep(_BASE_DELAY_S * (2**attempt))

    logger.error(
        "All %d fetch retries exhausted for mailbox %s", _MAX_RETRIES, mailbox.id
    )
    return None


def _filter_emails_by_target_email(
    emails: list[EmailMessage],
    target_email: str,
) -> list[EmailMessage]:
    """Filter emails whose subject or body contains ``target_email``.

    Enforces content-level matching beyond just SMTP envelope recipients:
    an email might be forwarded, aliased, or grouped under a distribution
    list while still being semantically addressed to the target user.
    """
    target_lower = target_email.strip().lower()
    return [
        e
        for e in emails
        if target_lower in e.subject.lower()
        or target_lower in e.body.lower()
        or target_lower in [r.lower() for r in e.to_recipients]
    ]


def extract_from_emails(
    emails: list[EmailMessage],
    service_key: str,
    window_minutes: int,
    target_email: str | None = None,
) -> ExtractedCode | None:
    """Run pure extractor on fetched emails. Returns ``ExtractedCode`` or ``None``.

    When ``target_email`` is provided, pre-filters emails to those whose
    subject, body, or ``to_recipients`` contain the target email — enforcing
    content-level semantic matching beyond SMTP envelope headers.
    """
    if target_email:
        emails = _filter_emails_by_target_email(emails, target_email)

    parsed: list[ParsedEmail] = [
        ParsedEmail(
            subject=e.subject,
            body=e.body,
            received_at=e.received_at,
        )
        for e in emails
    ]
    return extract_newest_from_emails(
        parsed, service_key, max_age_minutes=window_minutes
    )


async def complete_not_found(db: AsyncSession, job: MailLookupJob) -> None:
    """No extraction — complete with ``not_found``."""
    await mailbox_lookup_repository.transition_status(
        db, job, "completed", result_type="not_found"
    )


async def handle_deduped_result(
    db: AsyncSession,
    job: MailLookupJob,
    mailbox: TenantMailbox,
    emails: list[EmailMessage],
    extracted_value: str,
    extracted_type: str,
    service_key: str,
) -> None:
    """Dedupe check, record delivery, store ephemeral result."""
    match = _find_matching_email(emails, extracted_value)

    message_id = match.message_id if match else None
    sender = match.sender if match else None
    received_at_iso = (
        match.received_at.isoformat()
        if match and match.received_at
        else datetime.now(timezone.utc).isoformat()
    )
    subject = match.subject if match else ""

    fingerprint = compute_fingerprint(
        service_key=service_key,
        message_id=message_id,
        sender=sender,
        received_at_iso=received_at_iso,
        subject=subject,
        payload_normalized=extracted_value,
    )

    inserted = await mailbox_dedupe_repository.record_delivery_atomic(
        db,
        tenant_id=job.tenant_id,
        mailbox_id=mailbox.id,
        service_key=service_key,
        message_id=message_id,
        fingerprint=fingerprint,
    )

    if not inserted:
        await mailbox_lookup_repository.transition_status(
            db, job, "completed", result_type="duplicate_suppressed"
        )
        return

    store_result(job.id, extracted_type, extracted_value)

    await mailbox_lookup_repository.transition_status(
        db,
        job,
        "completed",
        result_type=extracted_type,
    )


def _find_matching_email(
    emails: list[EmailMessage],
    extracted_value: str,
) -> EmailMessage | None:
    """Find the email whose body contains the extracted value."""
    for e in emails:
        if extracted_value in e.body:
            return e
    return emails[0] if emails else None


async def fail_job(
    db: AsyncSession,
    job: MailLookupJob,
    error_code: str,
    error_detail_safe: str,
) -> None:
    """Transition job to failed with safe error info."""
    await mailbox_lookup_repository.transition_status(
        db,
        job,
        "failed",
        error_code=error_code,
        error_detail_safe=error_detail_safe,
    )


__all__ = [
    "resolve_provider_label",
    "fetch_with_retry",
    "extract_from_emails",
    "complete_not_found",
    "handle_deduped_result",
    "fail_job",
]
