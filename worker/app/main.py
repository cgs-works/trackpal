"""FastAPI application for the standalone lookup executor."""

from __future__ import annotations

import secrets
import time
from uuid import UUID

from fastapi import BackgroundTasks, FastAPI, HTTPException, Request
from pydantic import ValidationError

from app.config import ExecutorSettings
from app.pipeline.models import LookupCommand
from app.protocol.crypto import (
    decrypt_payload,
    derive_protocol_keys,
    verify_request_signature,
)
from app.protocol.models import EncryptedBody, ProtocolKeys
from app.protocol.replay import NonceCache
from app.runtime import CallbackContext, ExecutorRuntime

RUNTIME_VERSION = "0.1.0"
PROTOCOL_VERSION = 1
KEY_VERSION = 1
NONCE_TTL_SECONDS = 60
NONCE_MAX_ENTRIES = 10_000

_HEADER_ALIASES: dict[str, tuple[str, ...]] = {
    "executor_id": ("X-TrackPal-Executor-Id", "X-Executor-Id"),
    "key_version": ("X-TrackPal-Key-Version", "X-Key-Version"),
    "timestamp": ("X-TrackPal-Timestamp", "X-Timestamp"),
    "nonce": ("X-TrackPal-Nonce", "X-Nonce"),
    "signature": ("X-TrackPal-Signature", "X-Signature"),
}


def create_app(settings: ExecutorSettings, runtime: ExecutorRuntime) -> FastAPI:
    """Create an executor app with injectable runtime dependencies."""
    app = FastAPI(title="TrackPal Lookup Executor", version=RUNTIME_VERSION)
    keys = derive_protocol_keys(settings.executor_secret)
    nonce_cache = NonceCache(
        ttl_seconds=NONCE_TTL_SECONDS,
        max_entries=NONCE_MAX_ENTRIES,
    )

    @app.post("/v1/health/challenge")
    async def challenge(request: Request) -> dict[str, object]:
        """Authenticate and answer a backend protocol challenge."""
        payload = await _verify_and_decrypt(request, settings, keys, nonce_cache)
        challenge_value = payload.get("challenge")
        if not isinstance(challenge_value, str) or not challenge_value:
            raise HTTPException(status_code=422, detail="invalid challenge payload")
        return {
            "challenge": challenge_value,
            "protocol_version": PROTOCOL_VERSION,
            "runtime_version": RUNTIME_VERSION,
            "max_concurrency": settings.max_concurrency,
        }

    @app.post("/v1/jobs/execute", status_code=202)
    async def execute(
        request: Request,
        background_tasks: BackgroundTasks,
    ) -> dict[str, object]:
        """Authenticate, decrypt, reserve, and asynchronously execute a command."""
        payload = await _verify_and_decrypt(request, settings, keys, nonce_cache)
        try:
            command = LookupCommand.model_validate(payload)
        except ValidationError as exc:
            raise HTTPException(
                status_code=422, detail="invalid lookup command"
            ) from exc
        if (
            command.job_id is None
            or command.lease_id is None
            or command.callback_url is None
        ):
            raise HTTPException(
                status_code=422, detail="lookup command identity is required"
            )

        context = CallbackContext(
            callback_url=command.callback_url,
            job_id=command.job_id,
            lease_id=command.lease_id,
        )
        try:
            acceptance = await runtime.accept(command, context)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

        if acceptance.status == "busy":
            raise HTTPException(status_code=429, detail="executor capacity reached")
        if acceptance.status in {"duplicate", "conflict"}:
            raise HTTPException(
                status_code=409,
                detail=(
                    "duplicate execution"
                    if acceptance.status == "duplicate"
                    else "execution lease conflict"
                ),
            )

        background_tasks.add_task(runtime.execute, command, context)
        return {"accepted": True, "lease_id": str(acceptance.lease_id)}

    return app


async def _verify_and_decrypt(
    request: Request,
    settings: ExecutorSettings,
    keys: ProtocolKeys,
    nonce_cache: NonceCache,
) -> dict[str, object]:
    """Verify identity, freshness, signature, and replay before decryption."""
    body_bytes = await request.body()
    try:
        executor_id = UUID(_required_header(request, "executor_id"))
        key_version = int(_required_header(request, "key_version"))
        timestamp = int(_required_header(request, "timestamp"))
        nonce = _required_header(request, "nonce")
        signature = _required_header(request, "signature")
    except (TypeError, ValueError, HTTPException) as exc:
        raise HTTPException(status_code=401, detail="invalid protocol headers") from exc

    if executor_id != settings.executor_id or key_version != KEY_VERSION:
        raise HTTPException(status_code=401, detail="invalid protocol identity")
    try:
        verify_request_signature(
            request.method,
            request.url.path,
            executor_id,
            key_version,
            timestamp,
            nonce,
            body_bytes,
            signature,
            keys.signing,
            now=int(time.time()),
            max_skew_seconds=60,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=401, detail="invalid protocol signature"
        ) from exc
    if not nonce_cache.consume(nonce, now=int(time.time())):
        raise HTTPException(status_code=401, detail="replayed protocol nonce")

    try:
        encrypted = EncryptedBody.model_validate_json(body_bytes)
        return decrypt_payload(encrypted, keys.encryption)
    except Exception as exc:
        raise HTTPException(status_code=422, detail="invalid encrypted body") from exc


def _required_header(request: Request, name: str) -> str:
    """Read a required protocol header, allowing the short compatibility names."""
    for header_name in _HEADER_ALIASES[name]:
        value = request.headers.get(header_name)
        if value:
            return value
    raise HTTPException(status_code=401, detail="missing protocol header")


def _load_production_settings() -> ExecutorSettings:
    """Load settings while allowing imports without deployment environment variables."""
    try:
        return ExecutorSettings()
    except ValidationError as exc:
        if not all(error.get("type") == "missing" for error in exc.errors()):
            raise
        return ExecutorSettings(
            executor_id=UUID(int=0),
            executor_secret=secrets.token_urlsafe(32),
            max_concurrency=1,
        )


_production_settings = _load_production_settings()
app = create_app(
    _production_settings,
    ExecutorRuntime(_production_settings),
)

__all__ = ["app", "create_app"]
