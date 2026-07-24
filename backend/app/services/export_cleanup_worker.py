"""Background worker that periodically cleans up expired and failed export artifacts.

Runs every hour and:
1. Expired ready exports: deletes R2 objects and clears metadata.
2. Failed jobs older than 72 hours: clears error details and resets safe fields.
"""

from __future__ import annotations

import asyncio
import logging

from app.core.database import AsyncSessionLocal
from app.services.export_service import (
    cleanup_expired_exports,
    cleanup_stale_failed_jobs,
)

logger = logging.getLogger(__name__)

_CLEANUP_INTERVAL_S = 3600  # 1 hour


async def export_cleanup_loop() -> None:
    """Background task: periodically clean up expired/failed export artifacts."""
    logger.info("Starting export cleanup loop (interval=%ds)", _CLEANUP_INTERVAL_S)

    while True:
        try:
            await asyncio.sleep(_CLEANUP_INTERVAL_S)

            async with AsyncSessionLocal() as db:
                expired_count = await cleanup_expired_exports(db)
                if expired_count > 0:
                    logger.info("Cleaned up %d expired export(s)", expired_count)

                stale_count = await cleanup_stale_failed_jobs(db)
                if stale_count > 0:
                    logger.info("Cleaned up %d stale failed export(s)", stale_count)

        except asyncio.CancelledError:
            logger.info("Export cleanup loop cancelled")
            break
        except Exception:
            logger.exception("Unhandled error in export cleanup loop")
