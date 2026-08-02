"""SSRF-resistant validation for configured lookup executor URLs."""

from __future__ import annotations

import ipaddress
import socket
from dataclasses import dataclass
from typing import Iterable, Protocol
from urllib.parse import SplitResult, urlsplit


class ExecutorUrlError(ValueError):
    """Raised when an executor URL is unsafe or malformed."""


class AddressResolver(Protocol):
    """Resolve a host and port to address strings."""

    def __call__(self, host: str, port: int) -> Iterable[str]: ...


@dataclass(frozen=True)
class ValidatedExecutorUrl:
    """A URL whose authority and resolved connection address are safe."""

    base_url: str
    scheme: str
    hostname: str
    port: int
    addresses: tuple[str, ...]

    @property
    def url(self) -> str:
        """Return the normalized base URL for HTTP requests."""

        return self.base_url


def _system_resolver(host: str, port: int) -> list[str]:
    results = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    return [str(result[4][0]) for result in results]


def _resolve(resolver: AddressResolver | object, host: str, port: int) -> list[str]:
    try:
        if callable(resolver):
            try:
                values = resolver(host, port)
            except TypeError:
                values = resolver(host)
        elif hasattr(resolver, "resolve"):
            try:
                values = resolver.resolve(host, port)  # type: ignore[attr-defined]
            except TypeError:
                values = resolver.resolve(host)  # type: ignore[attr-defined]
        else:
            raise ExecutorUrlError("executor DNS resolver is invalid")
    except OSError as exc:
        raise ExecutorUrlError("executor hostname could not be resolved") from exc

    addresses: list[str] = []
    for value in values:
        if isinstance(value, str):
            candidate = value
        elif isinstance(value, tuple):
            candidate = str(value[0])
        elif hasattr(value, "host"):
            candidate = str(value.host)
        else:
            raise ExecutorUrlError("executor DNS returned an invalid address")
        try:
            ipaddress.ip_address(candidate)
        except ValueError as exc:
            raise ExecutorUrlError("executor DNS returned an invalid address") from exc
        if candidate not in addresses:
            addresses.append(candidate)
    return addresses


def _is_public_address(address: str) -> bool:
    ip = ipaddress.ip_address(address)
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        ip = ip.ipv4_mapped
    return bool(ip.is_global) and not ip.is_multicast and not ip.is_reserved


def _parse_url(base_url: str) -> SplitResult:
    parsed = urlsplit(base_url)
    if not parsed.scheme or not parsed.netloc or not parsed.hostname:
        raise ExecutorUrlError("executor URL must include a scheme and hostname")
    if parsed.username is not None or parsed.password is not None:
        raise ExecutorUrlError("executor URL must not contain credentials")
    if parsed.fragment:
        raise ExecutorUrlError("executor URL must not contain a fragment")
    if parsed.path not in {"", "/"} or parsed.query:
        raise ExecutorUrlError("executor URL must not contain a path or query")
    if parsed.scheme not in {"https", "http"}:
        raise ExecutorUrlError("executor URL scheme is not allowed")
    try:
        parsed.port
    except ValueError as exc:
        raise ExecutorUrlError("executor URL port is invalid") from exc
    return parsed


def validate_executor_url(
    base_url: str,
    transport_mode: str,
    resolver: AddressResolver | object | None = None,
) -> ValidatedExecutorUrl:
    """Validate an executor URL and return the addresses to which to pin it.

    HTTPS accepts hostnames and public IPs. The explicitly opt-in
    ``http_encrypted`` mode accepts only a literal public IP address.
    """

    parsed = _parse_url(base_url)
    hostname = parsed.hostname
    assert hostname is not None
    try:
        literal_ip = ipaddress.ip_address(hostname)
    except ValueError:
        literal_ip = None

    if parsed.scheme == "http":
        if transport_mode != "http_encrypted" or literal_ip is None:
            raise ExecutorUrlError("HTTP executors require an explicit public IP")
    elif transport_mode != "https":
        raise ExecutorUrlError("HTTPS executors require https transport mode")

    port = (
        parsed.port
        if parsed.port is not None
        else (443 if parsed.scheme == "https" else 80)
    )
    if not 1 <= port <= 65535:
        raise ExecutorUrlError("executor URL port is out of range")

    if literal_ip is not None:
        candidates = [str(literal_ip)]
    else:
        candidates = _resolve(resolver or _system_resolver, hostname, port)
    if not candidates:
        raise ExecutorUrlError("executor hostname did not resolve")
    if any(not _is_public_address(address) for address in candidates):
        raise ExecutorUrlError("executor hostname resolves to a non-public address")

    return ValidatedExecutorUrl(
        base_url=base_url.rstrip("/"),
        scheme=parsed.scheme,
        hostname=hostname,
        port=port,
        addresses=tuple(candidates),
    )


__all__ = [
    "AddressResolver",
    "ExecutorUrlError",
    "ValidatedExecutorUrl",
    "validate_executor_url",
]
