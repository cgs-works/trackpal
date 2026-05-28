"""Mail lookup worker — process on-demand lookup jobs asynchronously.

Entry points:
- ``process_job(db, job)`` — synchronous processing of one job.
- ``worker_loop(manager)`` — background asyncio task for continuous
  Redis queue consumption.  Started from the FastAPI lifespan.
"""

from app.services.mail_lookup_worker.ephemeral_cache import (
    get_result as get_ephemeral_result,
)
from app.services.mail_lookup_worker.fingerprint import compute_fingerprint
from app.services.mail_lookup_worker.providers import StubProvider, active_provider
from app.services.mail_lookup_worker.redis_queue import enqueue_job
from app.services.mail_lookup_worker.worker import process_job, worker_loop

__all__ = [
    "compute_fingerprint",
    "enqueue_job",
    "get_ephemeral_result",
    "process_job",
    "StubProvider",
    "active_provider",
    "worker_loop",
]
