"""Lookup job worker — process a single job through extract + dedupe.

Called from two paths:

1. **Background loop** (production) — FastAPI lifespan starts an
   asyncio task polling Redis, calling ``process_job`` per job.

2. **Direct call** (tests) — tests call ``process_job`` directly.
"""

from __future__ import annotations

import asyncio
import html
import logging
import re
import time
from uuid import UUID

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.core.metrics import metrics
from app.core.redis_client import RedisConnectionManager
from app.models import MailLookupJob
from app.repositories import mailbox_config_repository
from app.repositories import mailbox_lookup_repository
from app.services.mail_lookup_worker._helpers import (
    complete_not_found,
    extract_from_emails,
    fail_job,
    fetch_with_retry,
    handle_deduped_result,
    resolve_provider_label,
)
from app.services.mail_lookup_worker.providers import (
    NonTransientProviderError,
    RevokedMailboxError,
)
from app.services.mail_lookup_worker.r2_upload import upload_netflix_diagnostic
from app.services.mail_lookup_worker.redis_queue import dequeue_job

logger = logging.getLogger(__name__)

_POLL_INTERVAL_S = 1.0

_NON_TRANSIENT_SAFE_DETAIL: dict[str, str] = {
    "auth_failed": "Authentication failed — check mailbox credentials",
    "mailbox_revoked": "Mailbox revoked — reconnection required",
    "provider_config_error": "Mailbox configuration error — check settings",
    "permission_denied": "Access denied by email provider — check permissions",
}

_DESKTOP_CHROME_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36"


async def fetch_netflix_code_from_url(full_url: str) -> str | None:
    """Resolve Netflix travel verify URL to OTP code (4-6 digits).

    When extraction fails, uploads the raw HTML to Cloudflare R2 for debugging.
    """
    if "netflix.com/account/travel/verify" not in full_url:
        return None

    html_text = await _fetch_netflix_verify_html(full_url)
    if html_text is None:
        return None

    code = _extract_netflix_verify_code(html_text)
    if code is not None:
        return code

    # Diagnostic upload on failure — fire-and-forget via executor
    nftoken_match = re.search(r"nftoken=([^&]+)", full_url)
    nftoken_prefix = nftoken_match.group(1) if nftoken_match else ""

    loop = asyncio.get_running_loop()
    await loop.run_in_executor(
        None,
        upload_netflix_diagnostic,
        html_text,
        nftoken_prefix,
    )

    return None


async def _fetch_netflix_verify_html(url: str) -> str | None:
    for attempt in range(3):
        try:
            async with httpx.AsyncClient(
                follow_redirects=True,
                timeout=httpx.Timeout(10.0, connect=5.0),
                headers={"User-Agent": _DESKTOP_CHROME_UA},
            ) as client:
                resp = await client.get(url)

            if resp.status_code not in (200, 301, 302):
                logger.warning(
                    "[Netflix] Unexpected status %s for verify URL",
                    resp.status_code,
                )
                return None

            return resp.text
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "[Netflix] Verify fetch failed (attempt %d): %s", attempt + 1, exc
            )

    return None


def _extract_netflix_verify_code(html_text: str) -> str | None:
    def looks_like_placeholder(code: str) -> bool:
        if len(set(code)) == 1:
            return True
        return code in {
            "0000",
            "000000",
            "1234",
            "123456",
            "1111",
            "2222",
            "3333",
            "4444",
            "5555",
            "6666",
            "7777",
            "8888",
            "9999",
        }

    def digit_windows(digits_only: str):
        for size in (6, 5, 4):
            if len(digits_only) >= size:
                for i in range(len(digits_only) - size + 1):
                    yield digits_only[i : i + size]

    candidates: list[tuple[int, str]] = []

    for m in re.finditer(
        r'(?is)<div[^>]*data-uia="travel-verification-otp"[^>]*class="[^"]*challenge-code[^"]*"[^>]*>(.*?)</div>',
        html_text,
    ):
        inner = re.sub(r"<[^>]+>", " ", m.group(1))
        digits = re.sub(r"\D+", "", html.unescape(inner))
        for d in digit_windows(digits):
            if not looks_like_placeholder(d):
                candidates.append((10 if len(d) == 6 else 9, d))

    for m in re.finditer(
        r'(?is)(<div[^>]*data-uia="travel-verification-otp"[^>]*class="[^"]*challenge-code[^"]*"[^>]*>)',
        html_text,
    ):
        tag = m.group(1)
        for attr_digits in re.findall(
            r'aria-label="(\d{4,6})"|data-[a-zA-Z0-9_-]+="[^"]*(\d{4,6})[^"]*"',
            tag,
        ):
            dflat = next((x for x in attr_digits if x), None)
            if dflat and not looks_like_placeholder(dflat):
                candidates.append((8 if len(dflat) == 6 else 7, dflat))

    for m in re.finditer(
        r'(?is)<[^>]+data-uia="[^"]*(?:code|otp|pin)[^"]*"[^>]*>(.*?)</[^>]+>',
        html_text,
    ):
        inner = re.sub(r"<[^>]+>", " ", m.group(1))
        digits = re.sub(r"\D+", "", html.unescape(inner))
        for d in digit_windows(digits):
            if not looks_like_placeholder(d):
                candidates.append((5 + (3 if len(d) == 6 else 0), d))

    for m in re.finditer(
        r'(?is)<(span|div)[^>]+class="[^"]*(?:challenge-code|code|otp|pin)[^"]*"[^>]*>(.*?)</\1>',
        html_text,
    ):
        inner = re.sub(r"<[^>]+>", " ", m.group(2))
        digits = re.sub(r"\D+", "", html.unescape(inner))
        for d in digit_windows(digits):
            if not looks_like_placeholder(d):
                candidates.append((4 + (3 if len(d) == 6 else 0), d))

    if candidates:
        candidates.sort(key=lambda x: x[0], reverse=True)
        return candidates[0][1]

    for block in re.findall(r"(?is)<script[^>]*>\s*(\{.*?\})\s*</script>", html_text):
        for d in re.findall(r'"(?:otp|code|pin)[^"]*"\s*:\s*"?(\d{4,8})"?', block):
            if 4 <= len(d) <= 6 and not looks_like_placeholder(d):
                return d

    logger.warning("[Netflix] OTP not found in travel verify response")
    return None


def _safe_error_detail(error_code: str, raw_message: str) -> str:
    """Map non-transient error code to a safe detail message.

    Never includes raw exception messages that may contain secrets.
    Returns the safe mapping when known, otherwise a generic message.
    """
    return _NON_TRANSIENT_SAFE_DETAIL.get(
        error_code, "Provider error — check mailbox configuration"
    )


async def process_job(
    db: AsyncSession,
    job: MailLookupJob,
    window_minutes: int = 5,
) -> None:
    """Process one lookup job through the full pipeline.

    Handles state transitions:
    ``pending -> processing -> completed | failed``

    Caller commits the DB session after this returns.
    """
    start = time.monotonic()
    provider_label = resolve_provider_label(job)

    try:
        await mailbox_lookup_repository.transition_status(db, job, "processing")
        await db.flush()

        mailbox = await mailbox_config_repository.get_by_id(
            db, job.mailbox_id, tenant_id=job.tenant_id
        )
        if mailbox is None:
            await fail_job(
                db, job, "mailbox_not_found", "Mailbox not found or not accessible"
            )
            metrics.inc(
                "lookup_job_total",
                status="failed",
                provider=provider_label,
                service=job.service_key,
            )
            return

        target_email = job.target_email or None
        emails = await fetch_with_retry(
            mailbox, window_minutes, target_email=target_email, db=db
        )
        if emails is None:
            await fail_job(db, job, "fetch_failed", "Email fetch failed after retries")
            metrics.inc(
                "lookup_job_total",
                status="failed",
                provider=provider_label,
                service=job.service_key,
            )
            return

        result = extract_from_emails(
            emails, job.service_key, window_minutes, target_email=job.target_email
        )
        if result is None:
            await complete_not_found(db, job)
            metrics.inc(
                "lookup_job_total",
                status="completed",
                provider=provider_label,
                service=job.service_key,
                result="not_found",
            )
            return

        result_value = result.value
        result_type = str(result.result_type)

        if job.service_key == "netflix" and result_type == "url":
            resolved_code = await fetch_netflix_code_from_url(result_value)
            if not resolved_code:
                await complete_not_found(db, job)
                metrics.inc(
                    "lookup_job_total",
                    status="completed",
                    provider=provider_label,
                    service=job.service_key,
                    result="not_found",
                )
                return
            result_value = resolved_code
            result_type = "code"

        await handle_deduped_result(
            db,
            job,
            mailbox,
            emails,
            result_value,
            result_type,
            job.service_key,
        )

        elapsed = time.monotonic() - start
        metrics.record("lookup_job_latency", elapsed)
        metrics.inc(
            "lookup_job_total",
            status="completed",
            provider=provider_label,
            service=job.service_key,
            result=str(job.result_type or "ok"),
        )

    except RevokedMailboxError as exc:
        logger.warning(
            "Mailbox %s revoked while processing job %s", job.mailbox_id, job.id
        )
        metrics.inc(
            "lookup_job_total",
            status="failed",
            provider=provider_label,
            service=job.service_key,
        )
        try:
            await mailbox_lookup_repository.transition_status(
                db,
                job,
                "failed",
                error_code=exc.error_code,
                error_detail_safe="Mailbox revoked — reconnection required",
            )
        except Exception:
            logger.exception("Failed to mark job %s as failed (revoked)", job.id)

    except NonTransientProviderError as exc:
        logger.warning(
            "Non-transient provider error for job %s (code=%s): %s",
            job.id,
            exc.error_code,
            exc,
        )
        metrics.inc(
            "lookup_job_total",
            status="failed",
            provider=provider_label,
            service=job.service_key,
        )
        safe_detail = _safe_error_detail(exc.error_code, str(exc))
        try:
            await mailbox_lookup_repository.transition_status(
                db,
                job,
                "failed",
                error_code=exc.error_code,
                error_detail_safe=safe_detail,
            )
        except Exception:
            logger.exception("Failed to mark job %s as failed (non-transient)", job.id)

    except Exception:
        logger.exception("Unexpected error processing job %s", job.id)
        metrics.inc(
            "lookup_job_total",
            status="internal_error",
            provider=provider_label,
            service=job.service_key,
        )
        try:
            await mailbox_lookup_repository.transition_status(
                db,
                job,
                "failed",
                error_code="internal_error",
                error_detail_safe="Internal processing error",
            )
        except Exception:
            logger.exception(
                "Failed to mark job %s as failed (may already be terminal)", job.id
            )


async def worker_loop(
    manager: RedisConnectionManager | None,
) -> None:
    """Background asyncio task: poll Redis queue, process jobs.

    Runs until cancelled.  Each job gets its own DB session.
    """
    if manager is None:
        logger.info("Redis unavailable — lookup worker loop not started")
        return

    logger.info("Starting mail lookup worker loop")

    while True:
        try:
            job_id_str = await dequeue_job(manager, timeout=3)
            if job_id_str is None:
                await asyncio.sleep(_POLL_INTERVAL_S)
                continue

            job_id = UUID(job_id_str)
            logger.info("Worker picked up job %s", job_id)
            metrics.inc("lookup_jobs_dequeued")

            async with AsyncSessionLocal() as db:
                job = await mailbox_lookup_repository.get_job(db, job_id)
                if job is None:
                    logger.warning("Job %s not found in DB (already deleted?)", job_id)
                    metrics.inc("lookup_jobs_skipped", reason="not_found")
                    continue
                if job.status != "pending":
                    logger.warning(
                        "Job %s not pending (status=%s) — skipping",
                        job_id,
                        job.status,
                    )
                    metrics.inc("lookup_jobs_skipped", reason="not_pending")
                    continue

                await process_job(db, job)
                await db.commit()
                logger.info("Job %s processed successfully", job_id)

        except asyncio.CancelledError:
            logger.info("Worker loop cancelled")
            break
        except Exception:
            logger.exception("Unhandled error in worker loop")


__all__ = [
    "process_job",
    "worker_loop",
]
