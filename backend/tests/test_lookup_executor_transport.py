"""URL safety and HTTP transport tests for external lookup executors."""

import json
import time
from types import SimpleNamespace
from uuid import UUID, uuid4

import httpx
import pytest

from app.core.encryption import encrypt_value
from app.core.lookup_executor_protocol import derive_protocol_keys, sign_response
from app.schemas.lookup_executor_protocol import HandoffStatus
from app.services.lookup_executor_transport import http as http_transport_module
from app.services.lookup_executor_transport.http import HttpLookupExecutorTransport
from app.services.lookup_executor_transport.protocol import TransportError
from app.services.lookup_executor_transport.url_safety import (
    ExecutorUrlError,
    validate_executor_url,
)


PUBLIC_IP = "93.184.216.34"
EXECUTOR_ID = UUID("00000000-0000-0000-0000-000000000001")


def resolver_for(*addresses: str):
    def resolve(_host: str, _port: int) -> list[str]:
        return list(addresses)

    return resolve


def executor(
    base_url: str = f"https://{PUBLIC_IP}", transport_mode: str = "https"
) -> SimpleNamespace:
    return SimpleNamespace(
        id=EXECUTOR_ID,
        base_url=base_url,
        transport_mode=transport_mode,
        secret_encrypted=encrypt_value("executor-secret"),
        secret_version=1,
    )


def signed_response(
    item: SimpleNamespace,
    path: str,
    payload: dict[str, object],
    status_code: int = 200,
) -> httpx.Response:
    body = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
    timestamp = int(time.time())
    nonce = "response-nonce"
    signature = sign_response(
        "POST",
        path,
        item.id,
        item.secret_version,
        timestamp,
        nonce,
        body,
        derive_protocol_keys("executor-secret").signing,
    )
    return httpx.Response(
        status_code,
        content=body,
        headers={
            "Content-Type": "application/json",
            "X-TrackPal-Executor-Id": str(item.id),
            "X-TrackPal-Key-Version": str(item.secret_version),
            "X-TrackPal-Timestamp": str(timestamp),
            "X-TrackPal-Nonce": nonce,
            "X-TrackPal-Signature": signature,
        },
    )


@pytest.mark.parametrize(
    ("url", "mode", "addresses"),
    [
        ("https://executor.example.test", "https", [PUBLIC_IP]),
        (f"https://{PUBLIC_IP}", "https", [PUBLIC_IP]),
        (f"http://{PUBLIC_IP}", "http_encrypted", [PUBLIC_IP]),
    ],
)
def test_validate_executor_url_accepts_allowed_destinations(
    url: str, mode: str, addresses: list[str]
) -> None:
    validated = validate_executor_url(url, mode, resolver_for(*addresses))

    assert validated.base_url == url
    assert validated.addresses == tuple(addresses)


@pytest.mark.parametrize(
    "url", [f"https://{PUBLIC_IP}/prefix", f"https://{PUBLIC_IP}?token=1"]
)
def test_validate_executor_url_rejects_path_or_query_prefixes(url: str) -> None:
    with pytest.raises(ExecutorUrlError):
        validate_executor_url(url, "https", resolver_for(PUBLIC_IP))


def test_validate_executor_url_rejects_http_hostname_and_url_credentials() -> None:
    with pytest.raises(ExecutorUrlError):
        validate_executor_url(
            "http://executor.example.test", "http_encrypted", resolver_for(PUBLIC_IP)
        )
    with pytest.raises(ExecutorUrlError):
        validate_executor_url(
            f"https://user:password@{PUBLIC_IP}", "https", resolver_for(PUBLIC_IP)
        )
    with pytest.raises(ExecutorUrlError):
        validate_executor_url(
            f"https://{PUBLIC_IP}/#fragment", "https", resolver_for(PUBLIC_IP)
        )


@pytest.mark.parametrize(
    "address",
    [
        "127.0.0.1",
        "10.0.0.8",
        "172.16.2.4",
        "192.168.1.10",
        "169.254.1.20",
        "224.0.0.1",
        "192.0.2.10",
        "198.51.100.10",
        "169.254.169.254",
        "100.100.100.200",
    ],
)
def test_validate_executor_url_rejects_non_public_addresses(address: str) -> None:
    with pytest.raises(ExecutorUrlError):
        validate_executor_url(f"https://{address}", "https", resolver_for(address))


@pytest.mark.asyncio
async def test_http_transport_does_not_follow_redirects() -> None:
    item = executor()

    def handler(request: httpx.Request) -> httpx.Response:
        return signed_response(item, request.url.path, {}, status_code=307)

    transport = HttpLookupExecutorTransport(
        resolver=resolver_for(PUBLIC_IP), transport=httpx.MockTransport(handler)
    )
    with pytest.raises(httpx.HTTPStatusError):
        await transport.challenge(item, "probe")


@pytest.mark.asyncio
async def test_http_transport_authenticates_challenge_error_before_status() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"detail": "unauthorized"}, request=request)

    transport = HttpLookupExecutorTransport(
        resolver=resolver_for(PUBLIC_IP), transport=httpx.MockTransport(handler)
    )

    with pytest.raises(TransportError, match="invalid challenge"):
        await transport.challenge(executor(), "probe")


@pytest.mark.asyncio
async def test_http_transport_verifies_signed_challenge_response() -> None:
    item = executor()
    payload = {
        "challenge": "probe",
        "protocol_version": 1,
        "runtime_version": "0.1.0",
        "max_concurrency": 1,
    }
    transport = HttpLookupExecutorTransport(
        resolver=resolver_for(PUBLIC_IP),
        transport=httpx.MockTransport(
            lambda request: signed_response(item, request.url.path, payload)
        ),
    )

    result = await transport.challenge(item, "probe")

    assert result.executor_id == EXECUTOR_ID
    assert result.max_concurrency == 1


@pytest.mark.asyncio
async def test_http_transport_rejects_unsigned_challenge_response() -> None:
    transport = HttpLookupExecutorTransport(
        resolver=resolver_for(PUBLIC_IP),
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200,
                json={
                    "challenge": "probe",
                    "protocol_version": 1,
                    "runtime_version": "0.1.0",
                    "max_concurrency": 1,
                },
                request=request,
            )
        ),
    )

    with pytest.raises(TransportError, match="invalid challenge"):
        await transport.challenge(executor(), "probe")


@pytest.mark.asyncio
async def test_http_transport_maps_signed_handoff_statuses() -> None:
    item = executor()
    lease_id = uuid4()
    envelope = {"job_id": str(uuid4()), "lease_id": str(lease_id)}
    cases = [
        (202, {"accepted": True, "lease_id": str(lease_id)}, HandoffStatus.ACCEPTED),
        (
            409,
            {
                "duplicate": True,
                "detail": "duplicate execution",
                "lease_id": str(lease_id),
            },
            HandoffStatus.DUPLICATE_SAME_LEASE,
        ),
        (429, {"detail": "busy"}, HandoffStatus.BUSY),
        (401, {"detail": "unauthorized"}, HandoffStatus.SECURITY_ERROR),
        (422, {"detail": "invalid envelope"}, HandoffStatus.PROTOCOL_ERROR),
        (500, {"detail": "server error"}, HandoffStatus.TRANSPORT_ERROR),
    ]

    for status_code, payload, expected in cases:
        result = HttpLookupExecutorTransport._map_handoff_response(
            signed_response(item, "/v1/jobs/execute", payload, status_code), envelope
        )
        assert result.status is expected


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"detail": "duplicate execution"},
        {"detail": "duplicate execution", "lease_id": str(uuid4())},
    ],
)
def test_http_transport_rejects_ambiguous_duplicate_response(
    payload: dict[str, object],
) -> None:
    envelope = {"lease_id": str(uuid4())}
    response = httpx.Response(409, json=payload)

    result = HttpLookupExecutorTransport._map_handoff_response(response, envelope)

    assert result.status is HandoffStatus.PROTOCOL_ERROR


def test_http_transport_rejects_duplicate_text_without_explicit_evidence() -> None:
    lease_id = uuid4()
    response = httpx.Response(
        409,
        json={"detail": "duplicate execution", "lease_id": str(lease_id)},
    )

    result = HttpLookupExecutorTransport._map_handoff_response(
        response, {"lease_id": str(lease_id)}
    )

    assert result.status is HandoffStatus.PROTOCOL_ERROR


def test_http_transport_rejects_inconsistent_acceptance_lease() -> None:
    lease_id = uuid4()
    response = httpx.Response(202, json={"lease_id": str(uuid4())})

    result = HttpLookupExecutorTransport._map_handoff_response(
        response, {"lease_id": str(lease_id)}
    )

    assert result.status is HandoffStatus.PROTOCOL_ERROR


@pytest.mark.asyncio
async def test_http_transport_uses_pinned_transport_for_each_validated_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    item = executor("https://executor.example.test")
    lease_id = uuid4()
    created_addresses: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1/health/challenge":
            return signed_response(
                item,
                request.url.path,
                {
                    "challenge": "probe",
                    "protocol_version": 1,
                    "runtime_version": "0.1.0",
                    "max_concurrency": 1,
                },
            )
        return signed_response(
            item,
            request.url.path,
            {"accepted": True, "lease_id": str(lease_id)},
            status_code=202,
        )

    def pinned_transport(address: str) -> httpx.MockTransport:
        created_addresses.append(address)
        return httpx.MockTransport(handler)

    monkeypatch.setattr(
        http_transport_module, "_PinnedAsyncHTTPTransport", pinned_transport
    )
    transport = HttpLookupExecutorTransport(resolver=resolver_for(PUBLIC_IP))

    await transport.challenge(item, "probe")
    result = await transport.handoff(item, {"lease_id": str(lease_id)})

    assert result.status is HandoffStatus.ACCEPTED
    assert created_addresses == [PUBLIC_IP, PUBLIC_IP]


@pytest.mark.asyncio
async def test_http_transport_rejects_dns_rebinding_before_second_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0
    target = "https://executor.example.test"
    item = executor(target)

    def rebinding_resolver(_host: str, _port: int) -> list[str]:
        nonlocal calls
        calls += 1
        return [PUBLIC_IP] if calls == 1 else ["127.0.0.1"]

    def pinned_transport(address: str) -> httpx.MockTransport:
        assert address == PUBLIC_IP
        return httpx.MockTransport(
            lambda request: signed_response(
                item,
                request.url.path,
                {
                    "challenge": "probe",
                    "protocol_version": 1,
                    "runtime_version": "0.1.0",
                    "max_concurrency": 1,
                },
            )
        )

    monkeypatch.setattr(
        http_transport_module, "_PinnedAsyncHTTPTransport", pinned_transport
    )
    transport = HttpLookupExecutorTransport(resolver=rebinding_resolver)
    await transport.challenge(item, "probe")
    result = await transport.handoff(item, {"lease_id": str(uuid4())})

    assert result.status is HandoffStatus.SECURITY_ERROR
    assert calls == 2
