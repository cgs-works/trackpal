"""Signed, encrypted delivery of lookup outcomes to TrackPal."""

from __future__ import annotations

import asyncio
import secrets
import time
from collections.abc import Callable
from urllib.parse import urlsplit
from uuid import UUID

import httpx
from pydantic import BaseModel, ConfigDict

from app.config import ExecutorSettings
from app.pipeline.models import LookupOutcome
from app.protocol.crypto import derive_protocol_keys, encrypt_payload, sign_request
from app.protocol.models import EncryptedBody

CALLBACK_KEY_VERSION = 1
CALLBACK_MAX_ATTEMPTS = 3
CALLBACK_TIMEOUT_SECONDS = 20.0

HttpClientFactory = Callable[[], httpx.AsyncClient]


class CallbackEnvelope(BaseModel):
    """Encrypted callback payload with the identity needed by the backend."""

    model_config = ConfigDict(extra="forbid")

    job_id: UUID
    lease_id: UUID
    outcome: LookupOutcome


class CallbackClient:
    """Deliver callbacks without following redirects or retrying client errors."""

    def __init__(
        self,
        settings: ExecutorSettings | None = None,
        *,
        executor_id: UUID | None = None,
        executor_secret: str | None = None,
        http_client_factory: HttpClientFactory | None = None,
        max_attempts: int = CALLBACK_MAX_ATTEMPTS,
        retry_delay_seconds: float = 0.25,
    ) -> None:
        if settings is not None:
            if executor_id is not None or executor_secret is not None:
                raise ValueError(
                    "settings cannot be combined with executor credentials"
                )
            executor_id = settings.executor_id
            executor_secret = settings.executor_secret
        if executor_id is None or executor_secret is None:
            raise ValueError("executor credentials are required")
        if max_attempts <= 0:
            raise ValueError("max_attempts must be positive")
        self._executor_id = executor_id
        self._keys = derive_protocol_keys(executor_secret)
        self._http_client_factory = http_client_factory or _default_http_client
        self._max_attempts = max_attempts
        self._retry_delay_seconds = retry_delay_seconds

    async def send(
        self,
        callback_url: str,
        *,
        job_id: UUID,
        lease_id: UUID,
        outcome: LookupOutcome,
    ) -> bool:
        """Send one callback, retrying only connection and server failures."""
        path = urlsplit(callback_url).path or "/"
        body = EncryptedBody.model_validate(
            encrypt_payload(
                CallbackEnvelope(
                    job_id=job_id,
                    lease_id=lease_id,
                    outcome=outcome,
                ),
                self._keys.encryption,
            )
        )
        body_bytes = body.model_dump_json().encode("utf-8")
        timestamp = int(time.time())
        nonce = secrets.token_urlsafe(24)
        signature = sign_request(
            "POST",
            path,
            self._executor_id,
            CALLBACK_KEY_VERSION,
            timestamp,
            nonce,
            body_bytes,
            self._keys.signing,
        )
        headers = {
            "X-TrackPal-Executor-Id": str(self._executor_id),
            "X-TrackPal-Key-Version": str(CALLBACK_KEY_VERSION),
            "X-TrackPal-Timestamp": str(timestamp),
            "X-TrackPal-Nonce": nonce,
            "X-TrackPal-Signature": signature,
            "Content-Type": "application/json",
        }

        async with self._http_client_factory() as client:
            for attempt in range(self._max_attempts):
                try:
                    response = await client.post(
                        callback_url,
                        content=body_bytes,
                        headers=headers,
                        follow_redirects=False,
                        timeout=CALLBACK_TIMEOUT_SECONDS,
                    )
                except (httpx.ConnectError, httpx.ConnectTimeout):
                    if attempt + 1 >= self._max_attempts:
                        return False
                    await asyncio.sleep(self._retry_delay_seconds * (2**attempt))
                    continue

                if 200 <= response.status_code < 300:
                    return True
                if response.status_code < 500 or attempt + 1 >= self._max_attempts:
                    return False
                await asyncio.sleep(self._retry_delay_seconds * (2**attempt))
        return False


def _default_http_client() -> httpx.AsyncClient:
    """Create a callback client with redirects disabled at the transport seam."""
    return httpx.AsyncClient(follow_redirects=False)


__all__ = ["CallbackClient", "CallbackEnvelope"]
