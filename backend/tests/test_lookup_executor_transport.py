"""URL safety and HTTP transport tests for external lookup executors."""

from types import SimpleNamespace
from uuid import UUID, uuid4

import httpx
import pytest
import respx

from app.core.encryption import encrypt_value
from app.schemas.lookup_executor_protocol import HandoffStatus
from app.services.lookup_executor_transport.http import HttpLookupExecutorTransport
from app.services.lookup_executor_transport.url_safety import (
    ExecutorUrlError,
    validate_executor_url,
)


PUBLIC_IP = "93.184.216.34"


def resolver_for(*addresses: str):
    def resolve(_host: str, _port: int) -> list[str]:
        return list(addresses)

    return resolve


def executor(
    base_url: str = f"https://{PUBLIC_IP}", transport_mode: str = "https"
) -> SimpleNamespace:
    return SimpleNamespace(
        id=UUID("00000000-0000-0000-0000-000000000001"),
        base_url=base_url,
        transport_mode=transport_mode,
        secret_encrypted=encrypt_value("executor-secret"),
        secret_version=1,
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
    transport = HttpLookupExecutorTransport(resolver=resolver_for(PUBLIC_IP))
    target = f"https://{PUBLIC_IP}"
    with respx.mock(assert_all_called=True) as router:
        route = router.post(f"{target}/v1/health/challenge").respond(
            307, headers={"location": "https://internal.example.test"}
        )

        with pytest.raises(httpx.HTTPStatusError):
            await transport.challenge(executor(target), "probe")

        assert route.called


@pytest.mark.asyncio
async def test_http_transport_maps_handoff_statuses() -> None:
    transport = HttpLookupExecutorTransport(resolver=resolver_for(PUBLIC_IP))
    item = executor()
    lease_id = uuid4()
    envelope = {"job_id": str(uuid4()), "lease_id": str(lease_id)}

    with respx.mock(assert_all_called=True) as router:
        router.post(f"https://{PUBLIC_IP}/v1/jobs/execute").respond(
            202, json={"accepted": True, "lease_id": str(lease_id)}
        )
        result = await transport.handoff(item, envelope)

    assert result.status is HandoffStatus.ACCEPTED
    assert result.lease_id == lease_id


@pytest.mark.asyncio
async def test_http_transport_rejects_dns_rebinding_before_second_request() -> None:
    calls = 0
    target = "https://executor.example.test"

    def rebinding_resolver(_host: str, _port: int) -> list[str]:
        nonlocal calls
        calls += 1
        return [PUBLIC_IP] if calls == 1 else ["127.0.0.1"]

    transport = HttpLookupExecutorTransport(resolver=rebinding_resolver)
    item = executor(target)
    with respx.mock(assert_all_called=False) as router:
        router.post(f"{target}/v1/health/challenge").respond(
            200,
            json={
                "challenge": "probe",
                "protocol_version": 1,
                "runtime_version": "0.1.0",
                "max_concurrency": 1,
            },
        )
        await transport.challenge(item, "probe")
        result = await transport.handoff(item, {"lease_id": str(uuid4())})

    assert result.status is HandoffStatus.SECURITY_ERROR
    assert calls == 2
