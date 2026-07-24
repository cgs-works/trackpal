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
from app.services.export_cleanup_worker import export_cleanup_loop
from app.services.export_service import configure_export_service
from app.services.export_storage import ExportStorageConfig, R2ExportStorageAdapter
from app.services.export_worker import export_worker_loop
from app.services.mailbox_cleanup import cleanup_loop
from app.services.mail_lookup_worker import worker_loop
from app.services.step_up_limiter import StepUpRateLimiter

logger = logging.getLogger(__name__)

_worker_task: asyncio.Task | None = None
_cleanup_task: asyncio.Task | None = None
_export_worker_task: asyncio.Task | None = None
_export_cleanup_task: asyncio.Task | None = None


class PublicCatalogCORS(CORSMiddleware):
    """CORSMiddleware that skips the public catalog endpoint.

    The public catalog endpoint sets its own CORS headers dynamically
    based on the registered Allowed Origins for the API key. The global
    CORSMiddleware would duplicate these headers when the browser Origin
    matches settings.cors_origins, causing spec-violating behavior.

    This subclass bypasses CORS processing for the public catalog path
    so the endpoint retains full control of its CORS response.
    """

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http" and scope["path"].startswith("/api/v1/public/"):
            await self.app(scope, receive, send)
            return
        await super().__call__(scope, receive, send)


def _configure_export_runtime() -> None:
    storage_config = ExportStorageConfig.from_settings(settings)
    storage = R2ExportStorageAdapter(storage_config)
    limiter = StepUpRateLimiter(get_redis_manager())
    configure_export_service(storage, limiter)


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _worker_task, _cleanup_task, _export_worker_task, _export_cleanup_task

    # Startup
    validate_encryption_key()
    await init_redis()
    _configure_export_runtime()

    # Start background tasks
    manager = get_redis_manager()
    _worker_task = asyncio.create_task(worker_loop(manager))
    _cleanup_task = asyncio.create_task(cleanup_loop())
    _export_worker_task = asyncio.create_task(export_worker_loop())
    _export_cleanup_task = asyncio.create_task(export_cleanup_loop())
    logger.info("Background tasks started")

    yield

    # Shutdown
    _tasks = []
    for t in (_worker_task, _cleanup_task, _export_worker_task, _export_cleanup_task):
        if t is not None:
            t.cancel()
            _tasks.append(t)
    if _tasks:
        await asyncio.gather(*_tasks, return_exceptions=True)
        logger.info("Background tasks stopped")

    await close_redis()


app = FastAPI(title="TrackPal API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    PublicCatalogCORS,
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
