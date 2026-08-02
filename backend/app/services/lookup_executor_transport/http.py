"""HTTP adapter for the signed and encrypted Lookup Executor protocol."""

from __future__ import annotations

import json
import secrets
import time
from typing import Any
from uuid import UUID

import httpx
from pydantic import BaseModel

from app.core.encryption import decrypt_value
from app.core.lookup_executor_protocol import (
    derive_protocol_keys,
    encrypt_payload,
    sign_request,
)
from app.schemas.lookup_executor_protocol import (
    ChallengeResult,
    HandoffResult,
    HandoffStatus,
)
from app.services.lookup_executor_transport.protocol import TransportError
from app.services.lookup_executor_transport.url_safety import (
    AddressResolver,
    ExecutorUrlError,
    ValidatedExecutorUrl,
    validate_executor_url,
)

_CHALLENGE_PATH = "/v1/health/challenge"
_HANDOFF_PATH = "/v1/jobs/execute"


class HttpLookupExecutorTransport:
    """Send protocol v1 messages to a registered executor over HTTP(S)."""

    def __init__(
        self,
        resolver: AddressResolver | object | None = None,
        timeout: httpx.Timeout | float = 20.0,
    ) -> None:
        self._resolver = resolver
        self._timeout = timeout

    async def challenge(self, executor: Any, challenge: str) -> ChallengeResult:
        """Send a challenge and validate the executor's capabilities response."""

        validated = self._validate(executor)
        body, headers = self._signed_body(
            executor, _CHALLENGE_PATH, {"challenge": challenge}
        )
        try:
            async with httpx.AsyncClient(
                timeout=self._timeout, follow_redirects=False
            ) as client:
                response = await client.post(
                    self._endpoint(validated, _CHALLENGE_PATH),
                    content=body,
                    headers=headers,
                )
                response.raise_for_status()
        except httpx.RequestError as exc:
            raise TransportError("executor challenge transport failed") from exc

        try:
            payload = response.json()
            if not isinstance(payload, dict):
                raise TypeError("challenge response must be an object")
            if payload.get("challenge") != challenge:
                raise ValueError("challenge mismatch")
            return ChallengeResult(
                executor_id=UUID(str(executor.id)),
                protocol_version=int(payload["protocol_version"]),
                runtime_version=str(payload["runtime_version"]),
                max_concurrency=int(payload["max_concurrency"]),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise TransportError("executor returned an invalid challenge") from exc

    async def handoff(self, executor: Any, envelope: Any) -> HandoffResult:
        """Send an execution envelope and normalize its HTTP outcome."""

        try:
            validated = self._validate(executor)
        except ExecutorUrlError:
            return HandoffResult(
                status=HandoffStatus.SECURITY_ERROR,
                safe_error="executor URL failed security validation",
            )
        try:
            body, headers = self._signed_body(
                executor,
                _HANDOFF_PATH,
                self._payload(envelope),
            )
            async with httpx.AsyncClient(
                timeout=self._timeout, follow_redirects=False
            ) as client:
                response = await client.post(
                    self._endpoint(validated, _HANDOFF_PATH),
                    content=body,
                    headers=headers,
                )
        except (httpx.RequestError, ValueError, TypeError):
            return HandoffResult(
                status=HandoffStatus.TRANSPORT_ERROR,
                safe_error="executor handoff transport failed",
            )

        return self._map_handoff_response(response, envelope)

    def _validate(self, executor: Any) -> ValidatedExecutorUrl:
        return validate_executor_url(
            str(executor.base_url),
            str(executor.transport_mode),
            self._resolver,
        )

    @staticmethod
    def _endpoint(validated: ValidatedExecutorUrl, path: str) -> str:
        return f"{validated.base_url}{path}"

    @staticmethod
    def _payload(value: Any) -> dict[str, object]:
        if isinstance(value, BaseModel):
            payload = value.model_dump(mode="json")
        elif isinstance(value, dict):
            payload = dict(value)
        elif hasattr(value, "__dict__"):
            payload = dict(vars(value))
        else:
            raise TypeError("execution envelope must be an object")
        return payload

    @staticmethod
    def _secret(executor: Any) -> str:
        encrypted = getattr(executor, "secret_encrypted", None)
        secret = decrypt_value(encrypted)
        if not secret:
            raise ValueError("executor secret is unavailable")
        return secret

    def _signed_body(
        self,
        executor: Any,
        path: str,
        payload: dict[str, object],
    ) -> tuple[bytes, dict[str, str]]:
        keys = derive_protocol_keys(self._secret(executor))
        json_payload = json.loads(json.dumps(payload, default=str))
        encrypted = encrypt_payload(json_payload, keys.encryption)
        body = json.dumps(
            encrypted.model_dump(), separators=(",", ":"), sort_keys=True
        ).encode("utf-8")
        timestamp = int(time.time())
        nonce = secrets.token_urlsafe(24)
        key_version = int(executor.secret_version)
        executor_id = UUID(str(executor.id))
        signature = sign_request(
            "POST",
            path,
            executor_id,
            key_version,
            timestamp,
            nonce,
            body,
            keys.signing,
        )
        return body, {
            "Content-Type": "application/json",
            "X-TrackPal-Executor-Id": str(executor_id),
            "X-TrackPal-Key-Version": str(key_version),
            "X-TrackPal-Timestamp": str(timestamp),
            "X-TrackPal-Nonce": nonce,
            "X-TrackPal-Signature": signature,
        }

    @staticmethod
    def _map_handoff_response(response: httpx.Response, envelope: Any) -> HandoffResult:
        lease_id = _envelope_lease_id(envelope)
        try:
            raw_payload = response.json()
            payload = raw_payload if isinstance(raw_payload, dict) else {}
        except ValueError:
            payload = {}
        response_lease_id = _parse_uuid(payload.get("lease_id"))

        if response.status_code == 202:
            if response_lease_id is None:
                return HandoffResult(
                    status=HandoffStatus.PROTOCOL_ERROR,
                    safe_error="executor acceptance omitted lease identity",
                )
            return HandoffResult(
                status=HandoffStatus.ACCEPTED,
                lease_id=response_lease_id,
            )
        if response.status_code == 409:
            detail = str(payload.get("detail", "")).lower()
            if response_lease_id is not None and response_lease_id != lease_id:
                return HandoffResult(
                    status=HandoffStatus.PROTOCOL_ERROR,
                    lease_id=response_lease_id,
                    safe_error="executor reported a different lease",
                )
            if "conflict" in detail and "duplicate" not in detail:
                return HandoffResult(
                    status=HandoffStatus.PROTOCOL_ERROR,
                    lease_id=lease_id,
                    safe_error="executor reported a lease conflict",
                )
            return HandoffResult(
                status=HandoffStatus.DUPLICATE_SAME_LEASE,
                lease_id=lease_id,
            )
        if response.status_code == 429:
            return HandoffResult(
                status=HandoffStatus.BUSY,
                lease_id=lease_id,
                safe_error="executor capacity is busy",
            )
        if response.status_code in {401, 403}:
            return HandoffResult(
                status=HandoffStatus.SECURITY_ERROR,
                lease_id=lease_id,
                safe_error="executor rejected protocol authentication",
            )
        if response.status_code == 422:
            return HandoffResult(
                status=HandoffStatus.PROTOCOL_ERROR,
                lease_id=lease_id,
                safe_error="executor rejected the protocol envelope",
            )
        return HandoffResult(
            status=HandoffStatus.TRANSPORT_ERROR,
            lease_id=lease_id,
            safe_error="executor returned an unexpected HTTP status",
        )


def _parse_uuid(value: Any) -> UUID | None:
    if value is None:
        return None
    try:
        return UUID(str(value))
    except (ValueError, AttributeError):
        return None


def _envelope_lease_id(envelope: Any) -> UUID | None:
    value = (
        envelope.get("lease_id")
        if isinstance(envelope, dict)
        else getattr(envelope, "lease_id", None)
    )
    return _parse_uuid(value)


__all__ = ["HttpLookupExecutorTransport"]
