"""HTTP adapter for resuming suspended n8n lookup executions."""

from __future__ import annotations

import asyncio
from collections.abc import Mapping, Sequence
from typing import Any

import httpx


class HttpLookupResumeNotifier:
    """Deliver one terminal lookup payload to an n8n Wait resume URL."""

    def __init__(
        self,
        auth_token: str,
        *,
        client: httpx.AsyncClient | None = None,
        retry_delays: Sequence[float] = (0.25, 0.5, 1.0, 1.5, 2.0),
    ) -> None:
        self._auth_token = auth_token
        self._client = client
        self._retry_delays = tuple(retry_delays)

    async def notify(self, resume_url: str, payload: Mapping[str, Any]) -> bool:
        """POST a payload with bounded retries and redirects disabled."""
        owns_client = self._client is None
        client = self._client or httpx.AsyncClient(
            follow_redirects=False,
            timeout=httpx.Timeout(2.0, connect=1.0),
        )
        try:
            attempts = len(self._retry_delays) + 1
            for attempt in range(attempts):
                try:
                    response = await client.post(
                        resume_url,
                        json=dict(payload),
                        headers={"X-API-Key": self._auth_token},
                        follow_redirects=False,
                    )
                    if 200 <= response.status_code < 300:
                        return True
                    if response.status_code != 404 and response.status_code < 500:
                        return False
                except httpx.RequestError:
                    pass

                if attempt < len(self._retry_delays):
                    await asyncio.sleep(self._retry_delays[attempt])
            return False
        finally:
            if owns_client:
                await client.aclose()


__all__ = ["HttpLookupResumeNotifier"]
