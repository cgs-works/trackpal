"""Scheduled cleanup for expired mailbox lookup jobs and delivery logs.

Runs as a periodic background asyncio task from the FastAPI lifespan.
TTL/retention configurable via ``settings``.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.core.metrics import metrics
from app.repositories import mailbox_dedupe_repository, mailbox_lookup_repository

logger = logging.getLogger(__name__)

_CLEANUP_INTERVAL_SECONDS = 3600  # every hour


async def run_cleanup_once(db: AsyncSession) -> dict[str, int]:
    """Run one pass of mailbox cleanup.

    Returns dict of counts: ``expired_jobs``, ``deleted_jobs``,
    ``deleted_delivery_logs``.
    """
    results: dict[str, int] = {}

    # 1. Expire stale pending/processing jobs to timeout
    expired = await mailbox_lookup_repository.expire_stale_jobs(db)
    results["expired_jobs"] = expired

    # 2. Hard-delete expired jobs past TTL
    ttl = timedelta(minutes=settings.mailbox_lookup_job_ttl_minutes)
    cutoff_jobs = datetime.now(timezone.utc) - ttl
    deleted_jobs = await mailbox_lookup_repository.delete_expired_jobs(
        db, before=cutoff_jobs
    )
    results["deleted_jobs"] = deleted_jobs

    # 3. Hard-delete delivery log entries past retention
    retention_days = settings.mailbox_delivery_log_retention_days
    cutoff_logs = datetime.now(timezone.utc) - timedelta(days=retention_days)
    deleted_logs = await mailbox_dedupe_repository.delete_older_than(
        db, before=cutoff_logs
    )
    results["deleted_delivery_logs"] = deleted_logs

    return results


async def cleanup_loop() -> None:
    """Periodic background task: run cleanup every hour until cancelled.

    Intended to be started as an asyncio task from the FastAPI lifespan.
    """
    logger.info(
        "Mailbox cleanup loop starting (interval=%ds, "
        "job_ttl=%dm, delivery_retention=%dd)",
        _CLEANUP_INTERVAL_SECONDS,
        settings.mailbox_lookup_job_ttl_minutes,
        settings.mailbox_delivery_log_retention_days,
    )

    while True:
        try:
            async with AsyncSessionLocal() as db:
                counts = await run_cleanup_once(db)
                await db.commit()

            total = sum(counts.values())
            if total > 0:
                logger.info(
                    "Mailbox cleanup complete: expired_jobs=%d, "
                    "deleted_jobs=%d, deleted_delivery_logs=%d",
                    counts["expired_jobs"],
                    counts["deleted_jobs"],
                    counts["deleted_delivery_logs"],
                )
                metrics.inc("mailbox_cleanup_total", step="expire", status="ok")
                if counts["expired_jobs"]:
                    metrics.inc(
                        "mailbox_cleanup_items",
                        action="expire",
                        count=str(counts["expired_jobs"]),
                    )
                if counts["deleted_jobs"]:
                    metrics.inc(
                        "mailbox_cleanup_items",
                        action="delete_jobs",
                        count=str(counts["deleted_jobs"]),
                    )
                if counts["deleted_delivery_logs"]:
                    metrics.inc(
                        "mailbox_cleanup_items",
                        action="delete_delivery_logs",
                        count=str(counts["deleted_delivery_logs"]),
                    )

        except asyncio.CancelledError:
            logger.info("Mailbox cleanup loop cancelled")
            break
        except Exception:
            logger.exception("Mailbox cleanup loop error")
            metrics.inc("mailbox_cleanup_total", step="error")

        await asyncio.sleep(_CLEANUP_INTERVAL_SECONDS)

    logger.info("Mailbox cleanup loop stopped")


__all__ = ["cleanup_loop", "run_cleanup_once"]
