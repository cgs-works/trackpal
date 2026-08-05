"""Pure mail code extractor — no I/O, no side effects.

Given a subject + body (and optionally multiple candidates), applies
the versioned catalog rules to extract the most recent valid code or URL.

This is a pure function layer; all I/O (mailbox fetching, dedupe lookup)
happens in the worker.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import NamedTuple, TypedDict

from .catalog import get_service_entry
from .types import ResultType

MAX_CANDIDATE_AGE_MINUTES = 15


class ParsedEmail(TypedDict):
    """Minimum email representation for extraction."""

    subject: str
    body: str
    received_at: datetime


class ExtractedCode(NamedTuple):
    """Result of a successful extraction."""

    value: str
    result_type: ResultType
    service_key: str


class ExtractedEmail(NamedTuple):
    """Extraction result paired with its source email index."""

    result: ExtractedCode
    source_index: int


# ── Body normalisers ───────────────────────────────────────────────────────


def normalize_body(body: str, service_key: str) -> str:
    """Apply service-specific normalisation to the raw email body.

    Over time, new normalisation rules based on observed email variance
    should be added here — scoped to the affected service.
    """
    svc = get_service_entry(service_key)
    if svc is None:
        return body

    name = svc["service_name"]

    # Disney+ HTML emails sometimes insert spaces/newlines inside inline styles.
    # Removing whitespace across the board helps the regex match.
    if name == "Disney+":
        return body.replace(" ", "").replace("\r", "").replace("\n", "")

    # HBO Max inserts extra whitespace / line breaks between text and code.
    if name == "HBO Max":
        return re.sub(r"\s+", " ", body).strip()

    return body


# ── Subject matching ──────────────────────────────────────────────────────


def match_subject(subject: str, service_key: str) -> bool:
    """Check whether an email subject matches a service entry.

    Uses substring matching (legacy-compatible) — the subject must
    contain at least one of the entry's subject patterns.
    """
    entry = get_service_entry(service_key)
    if entry is None:
        return False
    return any(p in subject for p in entry["subject_patterns"])


# ── Body extraction ───────────────────────────────────────────────────────


def extract_from_body(
    body: str,
    service_key: str,
    *,
    subject: str | None = None,
) -> ExtractedCode | None:
    """Extract a code or URL from an email body.

    Steps:
    1. Optionally check subject matches (skip extraction when it doesn't)
    2. Apply service-specific body normalisation
    3. Try every extraction regex in definition order
    4. Return first match

    Returns ``None`` when no pattern matches.
    """
    if subject is not None and not match_subject(subject, service_key):
        return None

    entry = get_service_entry(service_key)
    if entry is None:
        return None

    # Try original body first, then normalised (legacy-compatible).
    # Normalisation (e.g. HBO whitespace collapse) can destroy multi-line
    # patterns like standalone-code-on-its-own-line.
    bodies_to_try = [body]
    normalised = normalize_body(body, service_key)
    if normalised != body:
        bodies_to_try.append(normalised)

    for candidate_body in bodies_to_try:
        for rule in entry["extraction_rules"]:
            m = re.search(rule["regex"], candidate_body)
            if m is not None:
                return ExtractedCode(
                    value=m.group(1),
                    result_type=rule["type"],
                    service_key=service_key,
                )

    return None


# ── Multi-email extraction (newest-valid) ────────────────────────────────


def extract_newest_from_emails(
    emails: list[ParsedEmail],
    service_key: str,
    *,
    max_age_minutes: int = MAX_CANDIDATE_AGE_MINUTES,
    now: datetime | None = None,
    search_after: datetime | None = None,
) -> ExtractedCode | None:
    """Extract the newest valid code from a sorted list of emails."""
    extracted = extract_newest_with_source(
        emails,
        service_key,
        max_age_minutes=max_age_minutes,
        now=now,
        search_after=search_after,
    )
    return extracted.result if extracted is not None else None


def extract_newest_with_source(
    emails: list[ParsedEmail],
    service_key: str,
    *,
    max_age_minutes: int = MAX_CANDIDATE_AGE_MINUTES,
    now: datetime | None = None,
    search_after: datetime | None = None,
) -> ExtractedEmail | None:
    """Extract the newest valid result and preserve its source index."""
    now = now or datetime.now(UTC)
    cutoff = (
        _ensure_utc_aware(search_after)
        if search_after is not None
        else now - __import__("datetime").timedelta(minutes=max_age_minutes)
    )

    candidates = [
        (index, email)
        for index, email in enumerate(emails)
        if _ensure_utc_aware(email["received_at"]) >= cutoff
    ]
    candidates.sort(
        key=lambda item: _ensure_utc_aware(item[1]["received_at"]),
        reverse=True,
    )

    for index, email in candidates:
        result = extract_from_body(email["body"], service_key, subject=email["subject"])
        if result is None:
            result = extract_from_body(
                email["subject"],
                service_key,
                subject=email["subject"],
            )
        if result is not None:
            return ExtractedEmail(result=result, source_index=index)

    return None


def _ensure_utc_aware(dt: datetime) -> datetime:
    """Normalize datetime to UTC-aware for safe comparisons/sorting."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)
