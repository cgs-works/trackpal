"""FastAPI application entrypoint — lifespan, middleware, routes."""

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.encryption import validate_encryption_key
from app.core.metrics import metrics
from app.core.redis_client import close_redis, get_redis_manager, init_redis
from app.services.mailbox_cleanup import cleanup_loop
from app.services.mail_lookup_worker import worker_loop

logger = logging.getLogger(__name__)

_worker_task: asyncio.Task | None = None
_cleanup_task: asyncio.Task | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _worker_task, _cleanup_task

    # Startup
    validate_encryption_key()
    await init_redis()

    # Start background tasks
    manager = get_redis_manager()
    _worker_task = asyncio.create_task(worker_loop(manager))
    _cleanup_task = asyncio.create_task(cleanup_loop())
    logger.info("Mailbox worker + cleanup background tasks started")

    yield

    # Shutdown
    if _worker_task is not None:
        _worker_task.cancel()
    if _cleanup_task is not None:
        _cleanup_task.cancel()
    if _worker_task is not None or _cleanup_task is not None:
        await asyncio.gather(
            *[t for t in (_worker_task, _cleanup_task) if t is not None],
            return_exceptions=True,
        )
        logger.info("Mailbox background tasks stopped")

    await close_redis()


app = FastAPI(title="TrackPal API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(api_router, prefix="/api/v1")


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/metrics")
async def metrics_endpoint():
    """Prometheus-style metrics for mailbox operations."""
    return Response(
        content=metrics.dump_prometheus(),
        media_type="text/plain; version=0.0.4",
    )
