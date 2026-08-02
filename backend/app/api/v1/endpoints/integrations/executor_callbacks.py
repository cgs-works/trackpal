"""Signed, encrypted callbacks from external lookup executors."""

from __future__ import annotations

import time
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request, status
from app.api.dependencies import DbDep
from app.core.database import set_internal_rls_context
from app.core.encryption import decrypt_value
from app.core.lookup_executor_protocol import (
    decrypt_payload,
    derive_protocol_keys,
    verify_request_signature,
)
from app.core.metrics import metrics
from app.repositories import lookup_executors_repository
from app.schemas.lookup_executor_protocol import (
    EncryptedBody,
    LookupCallbackEnvelope,
)
from app.services.lookup_execution_coordinator.coordinator import (
    CompletionAck,
    VerifiedCallback,
)
from app.services.lookup_execution_coordinator.runtime import (
    get_lookup_execution_coordinator,
)

router = APIRouter(tags=["integrations"])

_HEADER_ALIASES: dict[str, tuple[str, ...]] = {
    "executor_id": ("X-TrackPal-Executor-Id", "X-Executor-Id"),
    "key_version": ("X-TrackPal-Key-Version", "X-Key-Version"),
    "timestamp": ("X-TrackPal-Timestamp", "X-Timestamp"),
    "nonce": ("X-TrackPal-Nonce", "X-Nonce"),
    "signature": ("X-TrackPal-Signature", "X-Signature"),
}


@router.post("/executors/{executor_id}/jobs/{job_id}/complete")
async def complete_executor_callback(
    executor_id: UUID,
    job_id: UUID,
    request: Request,
    db: DbDep,
) -> dict[str, bool]:
    """Authenticate and apply one callback addressed to a leased job."""
    ack = await _process_callback(
        request,
        db,
        path_executor_id=executor_id,
        path_job_id=job_id,
    )
    return {"accepted": ack.accepted}


@router.post("/executor-callback")
async def complete_executor_callback_compat(
    request: Request,
    db: DbDep,
) -> dict[str, bool]:
    """Authenticate the compact callback route used by older executors."""
    ack = await _process_callback(request, db)
    return {"accepted": ack.accepted}


async def _process_callback(
    request: Request,
    db: DbDep,
    *,
    path_executor_id: UUID | None = None,
    path_job_id: UUID | None = None,
) -> CompletionAck:
    """Verify protocol metadata, decrypt the body, and delegate completion."""
    await set_internal_rls_context(db)
    body_bytes = await request.body()

    try:
        header_executor_id = UUID(_required_header(request, "executor_id"))
        key_version = int(_required_header(request, "key_version"))
        timestamp = int(_required_header(request, "timestamp"))
        nonce = _required_header(request, "nonce")
        signature = _required_header(request, "signature")
    except (HTTPException, TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid protocol headers",
        ) from exc

    if path_executor_id is not None and path_executor_id != header_executor_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid protocol identity",
        )

    executor = await lookup_executors_repository.get(db, header_executor_id)
    if executor is None or key_version != executor.secret_version:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid protocol identity",
        )
    secret = decrypt_value(executor.secret_encrypted)
    if not secret:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid protocol identity",
        )
    keys = derive_protocol_keys(secret)

    try:
        verify_request_signature(
            request.method,
            request.url.path,
            header_executor_id,
            key_version,
            timestamp,
            nonce,
            body_bytes,
            signature,
            keys.signing,
            now=int(time.time()),
            max_skew_seconds=settings_signature_skew_seconds(),
        )
    except (TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid protocol signature",
        ) from exc

    try:
        coordinator = get_lookup_execution_coordinator()
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="callback coordination unavailable",
        ) from exc
    try:
        consumed = await coordinator.consume_callback_nonce(
            header_executor_id,
            nonce,
            settings_callback_nonce_ttl_seconds(),
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="callback coordination unavailable",
        ) from exc
    if not consumed:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="replayed protocol nonce",
        )

    try:
        encrypted = EncryptedBody.model_validate_json(body_bytes)
        payload = decrypt_payload(encrypted, keys.encryption)
        envelope = LookupCallbackEnvelope.model_validate(payload)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="invalid encrypted callback body",
        ) from exc

    if path_job_id is not None and path_job_id != envelope.job_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid callback identity",
        )

    callback = VerifiedCallback(
        executor_id=header_executor_id,
        lease_id=envelope.lease_id,
        key_version=key_version,
        nonce=nonce,
        outcome=envelope.outcome,
    )
    ack = await coordinator.complete(envelope.job_id, callback)
    metrics.inc(
        "lookup_executor_callback", status="accepted" if ack.accepted else "ignored"
    )
    return ack


def _required_header(request: Request, name: str) -> str:
    """Read one required protocol header, including compatibility aliases."""
    for header_name in _HEADER_ALIASES[name]:
        value = request.headers.get(header_name)
        if value:
            return value
    raise HTTPException(status_code=401, detail="missing protocol header")


def settings_signature_skew_seconds() -> int:
    """Read the configured callback signature tolerance lazily for testability."""
    from app.core.config import settings

    return settings.lookup_signature_skew_seconds


def settings_callback_nonce_ttl_seconds() -> int:
    """Keep a nonce through the full lifetime of a future-dated signature."""
    skew_seconds = settings_signature_skew_seconds()
    return max(1, skew_seconds * 3)


__all__ = ["router"]
