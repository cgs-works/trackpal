"""Redis queue for lookup job coordination.

Uses a simple Redis list (``mailbox:lookup:queue``) with ``LPUSH``
for enqueue and blocking ``BRPOP`` for dequeue.  The worker loop runs
as a background asyncio task in the FastAPI lifespan.
"""

from __future__ import annotations

import logging
from uuid import UUID

from app.core.redis_client import RedisConnectionManager

logger = logging.getLogger(__name__)

QUEUE_KEY = "mailbox:lookup:queue"


async def enqueue_job(
    manager: RedisConnectionManager | None,
    job_id: UUID,
) -> bool:
    """Push ``job_id`` (UUID hex) to the lookup queue.

    Returns ``True`` on success, ``False`` when Redis is unavailable.
    """
    if manager is None:
        logger.warning("Redis unavailable — job %s not enqueued", job_id)
        return False

    try:
        await manager.execute(
            "enqueue_lookup",
            lambda r: r.lpush(QUEUE_KEY, str(job_id)),
        )
        logger.debug("Enqueued job %s", job_id)
        return True
    except Exception:
        logger.exception("Failed to enqueue job %s", job_id)
        return False


async def dequeue_job(
    manager: RedisConnectionManager,
    timeout: int = 3,
) -> str | None:
    """Blocking pop from the lookup queue (``BRPOP``).

    Returns the job ID string or ``None`` on timeout / error.
    """
    try:
        result: list[str] | None = await manager.execute(
            "dequeue_lookup",
            lambda r: r.brpop(QUEUE_KEY, timeout=timeout),
        )
        if result is not None and len(result) >= 2:
            return result[1]
    except Exception:
        logger.exception("Failed to dequeue lookup job")
    return None


async def queue_length(manager: RedisConnectionManager) -> int:
    """Return the current queue length (for monitoring)."""
    try:
        length: int = await manager.execute(
            "queue_length",
            lambda r: r.llen(QUEUE_KEY),
        )
        return length
    except Exception:
        return 0


__all__ = ["enqueue_job", "dequeue_job", "queue_length", "QUEUE_KEY"]
