"""HTTP adapter for the signed and encrypted Lookup Executor protocol."""

from __future__ import annotations

import json
import secrets
import ssl
import time
from contextlib import contextmanager
from types import TracebackType
from typing import Any, AsyncIterator, Iterable
from uuid import UUID

import httpcore
import httpx
from pydantic import BaseModel

from app.core.encryption import decrypt_value
from app.core.lookup_executor_protocol import (
    derive_protocol_keys,
    encrypt_payload,
    sign_request,
    verify_response_signature,
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
_RESPONSE_HEADERS = (
    "X-TrackPal-Executor-Id",
    "X-TrackPal-Key-Version",
    "X-TrackPal-Timestamp",
    "X-TrackPal-Nonce",
    "X-TrackPal-Signature",
)


class _PinnedNetworkBackend(httpcore.AsyncNetworkBackend):
    """Connect to a validated address while retaining the request hostname."""

    def __init__(self, address: str) -> None:
        self._address = address
        self._backend = httpcore.AnyIOBackend()

    async def connect_tcp(
        self,
        host: str,
        port: int,
        timeout: float | None = None,
        local_address: str | None = None,
        socket_options: Iterable[httpcore.SOCKET_OPTION] | None = None,
    ) -> httpcore.AsyncNetworkStream:
        del host
        return await self._backend.connect_tcp(
            self._address,
            port,
            timeout=timeout,
            local_address=local_address,
            socket_options=socket_options,
        )

    async def connect_unix_socket(
        self,
        path: str,
        timeout: float | None = None,
        socket_options: Iterable[httpcore.SOCKET_OPTION] | None = None,
    ) -> httpcore.AsyncNetworkStream:
        return await self._backend.connect_unix_socket(
            path, timeout=timeout, socket_options=socket_options
        )

    async def sleep(self, seconds: float) -> None:
        await self._backend.sleep(seconds)


class _AsyncResponseStream(httpx.AsyncByteStream):
    """Adapt an httpcore response stream to the httpx transport interface."""

    def __init__(self, stream: AsyncIterator[bytes]) -> None:
        self._stream = stream

    async def __aiter__(self) -> AsyncIterator[bytes]:
        async for part in self._stream:
            yield part

    async def aclose(self) -> None:
        close = getattr(self._stream, "aclose", None)
        if close is not None:
            await close()


class _PinnedAsyncHTTPTransport(httpx.AsyncBaseTransport):
    """Minimal HTTPX transport with a fixed TCP destination address."""

    def __init__(self, address: str) -> None:
        self._pool = httpcore.AsyncConnectionPool(
            ssl_context=ssl.create_default_context(),
            max_connections=100,
            max_keepalive_connections=20,
            keepalive_expiry=5.0,
            network_backend=_PinnedNetworkBackend(address),
        )

    async def __aenter__(self) -> _PinnedAsyncHTTPTransport:
        await self._pool.__aenter__()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None = None,
        exc_value: BaseException | None = None,
        traceback: TracebackType | None = None,
    ) -> None:
        with _map_httpcore_exceptions():
            await self._pool.__aexit__(exc_type, exc_value, traceback)

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        req = httpcore.Request(
            method=request.method,
            url=httpcore.URL(
                scheme=request.url.raw_scheme,
                host=request.url.raw_host,
                port=request.url.port,
                target=request.url.raw_path,
            ),
            headers=request.headers.raw,
            content=request.stream,
            extensions=request.extensions,
        )
        with _map_httpcore_exceptions():
            response = await self._pool.handle_async_request(req)
        return httpx.Response(
            status_code=response.status,
            headers=response.headers,
            stream=_AsyncResponseStream(response.stream),
            extensions=response.extensions,
            request=request,
        )

    async def aclose(self) -> None:
        await self._pool.aclose()


@contextmanager
def _map_httpcore_exceptions() -> Any:
    """Translate httpcore errors to the public httpx exception hierarchy."""

    try:
        yield
    except httpcore.ConnectError as exc:
        raise httpx.ConnectError(str(exc)) from exc
    except httpcore.ReadError as exc:
        raise httpx.ReadError(str(exc)) from exc
    except httpcore.WriteError as exc:
        raise httpx.WriteError(str(exc)) from exc
    except httpcore.PoolTimeout as exc:
        raise httpx.PoolTimeout(str(exc)) from exc
    except httpcore.TimeoutException as exc:
        raise httpx.TimeoutException(str(exc)) from exc
    except httpcore.NetworkError as exc:
        raise httpx.NetworkError(str(exc)) from exc


class HttpLookupExecutorTransport:
    """Send protocol v1 messages to a registered executor over HTTP(S)."""

    def __init__(
        self,
        resolver: AddressResolver | object | None = None,
        timeout: httpx.Timeout | float = 20.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._resolver = resolver
        self._timeout = timeout
        self._transport = transport

    async def challenge(self, executor: Any, challenge: str) -> ChallengeResult:
        """Send a challenge and validate the executor's capabilities response."""

        validated = self._validate(executor)
        body, headers = self._signed_body(
            executor, _CHALLENGE_PATH, {"challenge": challenge}
        )
        try:
            response = await self._post(validated, _CHALLENGE_PATH, body, headers)
            response.raise_for_status()
        except httpx.RequestError as exc:
            raise TransportError("executor challenge transport failed") from exc
        except httpx.HTTPStatusError:
            raise

        try:
            self._verify_response(executor, _CHALLENGE_PATH, response)
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
            body, headers = self._signed_body(
                executor,
                _HANDOFF_PATH,
                self._payload(envelope),
            )
            response = await self._post(validated, _HANDOFF_PATH, body, headers)
        except ExecutorUrlError:
            return HandoffResult(
                status=HandoffStatus.SECURITY_ERROR,
                safe_error="executor URL failed security validation",
            )
        except httpx.RequestError:
            return HandoffResult(
                status=HandoffStatus.TRANSPORT_ERROR,
                safe_error="executor handoff transport failed",
            )
        except (ValueError, TypeError):
            return HandoffResult(
                status=HandoffStatus.TRANSPORT_ERROR,
                safe_error="executor handoff could not be prepared",
            )

        try:
            self._verify_response(executor, _HANDOFF_PATH, response)
        except (ValueError, TypeError):
            return HandoffResult(
                status=HandoffStatus.SECURITY_ERROR,
                safe_error="executor response signature verification failed",
            )
        return self._map_handoff_response(response, envelope)

    async def _post(
        self,
        validated: ValidatedExecutorUrl,
        path: str,
        body: bytes,
        headers: dict[str, str],
    ) -> httpx.Response:
        endpoint = self._endpoint(validated, path)
        transport = self._transport or _PinnedAsyncHTTPTransport(validated.addresses[0])
        async with httpx.AsyncClient(
            transport=transport,
            timeout=self._timeout,
            follow_redirects=False,
            trust_env=False,
        ) as client:
            return await client.post(endpoint, content=body, headers=headers)

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

    def _verify_response(
        self, executor: Any, path: str, response: httpx.Response
    ) -> None:
        values = [response.headers.get(header) for header in _RESPONSE_HEADERS]
        if any(value is None or not value for value in values):
            raise ValueError("executor response signature headers are missing")
        executor_id_text, version_text, timestamp_text, nonce, signature = values
        assert executor_id_text is not None
        assert version_text is not None
        assert timestamp_text is not None
        assert nonce is not None
        assert signature is not None
        executor_id = UUID(executor_id_text)
        key_version = int(version_text)
        if executor_id != UUID(str(executor.id)):
            raise ValueError("executor response identity mismatch")
        if key_version != int(executor.secret_version):
            raise ValueError("executor response key version mismatch")
        verify_response_signature(
            "POST",
            path,
            executor_id,
            key_version,
            int(timestamp_text),
            nonce,
            response.content,
            signature,
            derive_protocol_keys(self._secret(executor)).signing,
            now=int(time.time()),
            max_skew_seconds=60,
        )

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
            if lease_id is None or response_lease_id != lease_id:
                return HandoffResult(
                    status=HandoffStatus.PROTOCOL_ERROR,
                    lease_id=response_lease_id,
                    safe_error="executor acceptance lease does not match request",
                )
            return HandoffResult(
                status=HandoffStatus.ACCEPTED,
                lease_id=response_lease_id,
            )
        if response.status_code == 409:
            detail = str(payload.get("detail", "")).lower()
            duplicate = payload.get("duplicate") is True or "duplicate" in detail
            if (
                not duplicate
                or lease_id is None
                or response_lease_id is None
                or response_lease_id != lease_id
            ):
                return HandoffResult(
                    status=HandoffStatus.PROTOCOL_ERROR,
                    lease_id=response_lease_id,
                    safe_error="executor did not provide matching duplicate evidence",
                )
            return HandoffResult(
                status=HandoffStatus.DUPLICATE_SAME_LEASE,
                lease_id=response_lease_id,
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
    except (TypeError, ValueError, AttributeError):
        return None


def _envelope_lease_id(envelope: Any) -> UUID | None:
    value = (
        envelope.get("lease_id")
        if isinstance(envelope, dict)
        else getattr(envelope, "lease_id", None)
    )
    return _parse_uuid(value)


__all__ = ["HttpLookupExecutorTransport"]
