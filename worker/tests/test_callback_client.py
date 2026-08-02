from uuid import UUID

import httpx
import pytest

from app.callback_client import CallbackClient
from app.pipeline.models import LookupOutcome
from app.protocol.crypto import (
    decrypt_payload,
    derive_protocol_keys,
    verify_request_signature,
)
from app.protocol.models import EncryptedBody

EXECUTOR_ID = UUID("00000000-0000-0000-0000-000000000001")
CALLBACK_URL = "https://backend.example.test/api/v1/callbacks/job-1"
JOB_ID = UUID("00000000-0000-0000-0000-000000000010")
LEASE_ID = UUID("00000000-0000-0000-0000-000000000011")
SECRET = "executor-secret"


def _client(handler: httpx.AsyncBaseTransport, **kwargs: object) -> CallbackClient:
    return CallbackClient(
        executor_id=EXECUTOR_ID,
        executor_secret=SECRET,
        http_client_factory=lambda: httpx.AsyncClient(transport=handler),
        **kwargs,
    )


async def _send(client: CallbackClient, callback_url: str = CALLBACK_URL) -> bool:
    return await client.send(
        callback_url,
        job_id=JOB_ID,
        lease_id=LEASE_ID,
        outcome=LookupOutcome.not_found(),
    )


@pytest.mark.asyncio
async def test_callback_client_sends_signed_encrypted_outcome() -> None:
    requests: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"accepted": True})

    acknowledged = await _send(_client(httpx.MockTransport(handler)))

    assert acknowledged is True
    request = requests[0]
    assert request.headers["X-TrackPal-Executor-Id"] == str(EXECUTOR_ID)
    assert request.headers["X-TrackPal-Key-Version"] == "1"
    assert request.headers["X-TrackPal-Timestamp"].isdigit()
    assert request.headers["X-TrackPal-Nonce"]
    assert request.headers["X-TrackPal-Signature"]
    body = EncryptedBody.model_validate_json(request.content)
    payload = decrypt_payload(body, derive_protocol_keys(SECRET).encryption)
    assert payload["job_id"] == str(JOB_ID)
    assert payload["lease_id"] == str(LEASE_ID)
    assert payload["outcome"] == {
        "kind": "not_found",
        "result_type": None,
        "result_value": None,
        "message_id": None,
        "fingerprint": None,
        "error_code": None,
        "error_detail": None,
    }
    verify_request_signature(
        request.method,
        request.url.path,
        EXECUTOR_ID,
        int(request.headers["X-TrackPal-Key-Version"]),
        int(request.headers["X-TrackPal-Timestamp"]),
        request.headers["X-TrackPal-Nonce"],
        request.content,
        request.headers["X-TrackPal-Signature"],
        derive_protocol_keys(SECRET).signing,
        now=int(request.headers["X-TrackPal-Timestamp"]),
        max_skew_seconds=0,
    )


@pytest.mark.asyncio
async def test_callback_signature_uses_path_without_query_string() -> None:
    requests: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(204)

    acknowledged = await _send(
        _client(httpx.MockTransport(handler)),
        f"{CALLBACK_URL}?token=callback-token",
    )

    assert acknowledged is True
    request = requests[0]
    verify_request_signature(
        request.method,
        request.url.path,
        EXECUTOR_ID,
        int(request.headers["X-TrackPal-Key-Version"]),
        int(request.headers["X-TrackPal-Timestamp"]),
        request.headers["X-TrackPal-Nonce"],
        request.content,
        request.headers["X-TrackPal-Signature"],
        derive_protocol_keys(SECRET).signing,
        now=int(request.headers["X-TrackPal-Timestamp"]),
        max_skew_seconds=0,
    )


@pytest.mark.asyncio
async def test_callback_client_retries_server_errors() -> None:
    statuses = iter([503, 200])
    calls = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(next(statuses), json={"accepted": calls == 2})

    acknowledged = await _send(
        _client(httpx.MockTransport(handler), retry_delay_seconds=0)
    )

    assert acknowledged is True
    assert calls == 2


@pytest.mark.asyncio
async def test_callback_client_does_not_retry_client_errors() -> None:
    calls = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(400)

    acknowledged = await _send(
        _client(httpx.MockTransport(handler), retry_delay_seconds=0)
    )

    assert acknowledged is False
    assert calls == 1


@pytest.mark.asyncio
async def test_callback_client_retries_connection_errors() -> None:
    calls = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise httpx.ConnectError("connection failed", request=request)
        return httpx.Response(200, json={"accepted": True})

    acknowledged = await _send(
        _client(httpx.MockTransport(handler), retry_delay_seconds=0)
    )

    assert acknowledged is True
    assert calls == 2


@pytest.mark.asyncio
async def test_callback_client_does_not_follow_or_retry_redirects() -> None:
    calls = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(307, headers={"Location": "/elsewhere"})

    acknowledged = await _send(
        _client(httpx.MockTransport(handler), retry_delay_seconds=0),
    )

    assert acknowledged is False
    assert calls == 1


@pytest.mark.asyncio
async def test_callback_client_treats_accepted_false_as_final_ack() -> None:
    calls = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, json={"accepted": False})

    acknowledged = await _send(
        _client(httpx.MockTransport(handler), retry_delay_seconds=0)
    )

    assert acknowledged is True
    assert calls == 1
