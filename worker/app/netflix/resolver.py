"""Netflix travel-verification URL resolver."""

from __future__ import annotations

import asyncio
import html
import re
from collections.abc import Iterator
from typing import Protocol

import httpx

from .r2_diagnostics import R2Diagnostics

DESKTOP_CHROME_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36"
)


class NetflixResolverPort(Protocol):
    """Port used by the pipeline for Netflix URL resolution."""

    async def resolve(self, full_url: str) -> str | None:
        """Resolve a Netflix travel verification URL to an OTP."""


class NetflixResolver:
    """Resolve Netflix verification pages using an injected HTTP client."""

    def __init__(
        self,
        client: httpx.AsyncClient | None = None,
        diagnostics: R2Diagnostics | None = None,
    ) -> None:
        self._client = client
        self._diagnostics = diagnostics or R2Diagnostics()

    async def resolve(self, full_url: str) -> str | None:
        """Fetch and parse a Netflix travel verification page."""
        if "netflix.com/account/travel/verify" not in full_url:
            return None

        if self._client is not None:
            html_text = await self._fetch_html(self._client, full_url)
        else:
            timeout = httpx.Timeout(10.0, connect=5.0)
            async with httpx.AsyncClient(
                follow_redirects=True,
                timeout=timeout,
                headers={"User-Agent": DESKTOP_CHROME_UA},
            ) as client:
                html_text = await self._fetch_html(client, full_url)

        if html_text is None:
            return None

        code = extract_netflix_verify_code(html_text)
        if code is not None:
            return code

        token_match = re.search(r"nftoken=([^&]+)", full_url)
        token_prefix = token_match.group(1) if token_match else ""
        try:
            await asyncio.to_thread(self._diagnostics.upload, html_text, token_prefix)
        except Exception:  # noqa: BLE001 - diagnostics are best effort
            return None
        return None

    async def _fetch_html(
        self,
        client: httpx.AsyncClient,
        url: str,
    ) -> str | None:
        for _attempt in range(3):
            try:
                response = await client.get(
                    url,
                    headers={"User-Agent": DESKTOP_CHROME_UA},
                )
                if response.status_code not in (200, 301, 302):
                    return None
                return response.text
            except Exception:  # noqa: BLE001,S112 - HTTP retry boundary
                continue
        return None


def _looks_like_placeholder(code: str) -> bool:
    return len(set(code)) == 1 or code in {
        "0000",
        "000000",
        "1234",
        "123456",
        "1111",
        "2222",
        "3333",
        "4444",
        "5555",
        "6666",
        "7777",
        "8888",
        "9999",
    }


def _digit_windows(digits_only: str) -> Iterator[str]:
    for size in (6, 5, 4):
        if len(digits_only) >= size:
            for index in range(len(digits_only) - size + 1):
                yield digits_only[index : index + size]


def extract_netflix_verify_code(html_text: str) -> str | None:
    """Extract a non-placeholder four-to-six-digit Netflix OTP."""
    candidates: list[tuple[int, str]] = []

    for match in re.finditer(
        r'(?is)<div[^>]*data-uia="travel-verification-otp"[^>]*'
        r'class="[^"]*challenge-code[^"]*"[^>]*>(.*?)</div>',
        html_text,
    ):
        inner = re.sub(r"<[^>]+>", " ", match.group(1))
        digits = re.sub(r"\D+", "", html.unescape(inner))
        for digit in _digit_windows(digits):
            if not _looks_like_placeholder(digit):
                candidates.append((10 if len(digit) == 6 else 9, digit))

    for match in re.finditer(
        r'(?is)(<div[^>]*data-uia="travel-verification-otp"[^>]*'
        r'class="[^"]*challenge-code[^"]*"[^>]*>)',
        html_text,
    ):
        for attributes in re.findall(
            r'aria-label="(\d{4,6})"|data-[a-zA-Z0-9_-]+="[^"]*(\d{4,6})[^"]*"',
            match.group(1),
        ):
            attribute_digit: str | None = None
            for value in attributes:
                if value:
                    attribute_digit = str(value)
                    break
            if attribute_digit and not _looks_like_placeholder(attribute_digit):
                candidates.append(
                    (
                        8 if len(attribute_digit) == 6 else 7,
                        attribute_digit,
                    )
                )

    for match in re.finditer(
        r'(?is)<[^>]+data-uia="[^"]*(?:code|otp|pin)[^"]*"[^>]*>'
        r"(.*?)</[^>]+>",
        html_text,
    ):
        inner = re.sub(r"<[^>]+>", " ", match.group(1))
        digits = re.sub(r"\D+", "", html.unescape(inner))
        for digit in _digit_windows(digits):
            if not _looks_like_placeholder(digit):
                candidates.append((5 + (3 if len(digit) == 6 else 0), digit))

    for match in re.finditer(
        r'(?is)<(span|div)[^>]+class="[^"]*(?:challenge-code|code|otp|pin)'
        r'[^"]*"[^>]*>(.*?)</\1>',
        html_text,
    ):
        inner = re.sub(r"<[^>]+>", " ", match.group(2))
        digits = re.sub(r"\D+", "", html.unescape(inner))
        for digit in _digit_windows(digits):
            if not _looks_like_placeholder(digit):
                candidates.append((4 + (3 if len(digit) == 6 else 0), digit))

    if candidates:
        candidates.sort(key=lambda item: item[0], reverse=True)
        return candidates[0][1]

    for block in re.findall(r"(?is)<script[^>]*>\s*(\{.*?\})\s*</script>", html_text):
        for digit in re.findall(r'"(?:otp|code|pin)[^"]*"\s*:\s*"?(\d{4,8})"?', block):
            if 4 <= len(digit) <= 6 and not _looks_like_placeholder(digit):
                return str(digit)
    return None


async def fetch_netflix_code_from_url(
    full_url: str,
    *,
    client: httpx.AsyncClient | None = None,
    diagnostics: R2Diagnostics | None = None,
) -> str | None:
    """Resolve a URL using an explicitly injectable resolver dependency."""
    return await NetflixResolver(client, diagnostics).resolve(full_url)


__all__ = [
    "NetflixResolver",
    "NetflixResolverPort",
    "extract_netflix_verify_code",
    "fetch_netflix_code_from_url",
]
