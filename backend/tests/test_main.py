"""Tests for public application-level routes."""

import pytest

pytestmark = pytest.mark.asyncio


async def test_root_redirects_to_trackpal_landing(client):
    response = await client.get("/", follow_redirects=False)

    assert response.status_code == 308
    assert response.headers["location"] == "https://trackpal.wilfredocamacho.dev"


async def test_lookup_runtime_uses_configured_cold_start_handoff_timeout():
    import inspect

    from app.main import lifespan

    source = inspect.getsource(lifespan)

    assert (
        "HttpLookupExecutorTransport(\n"
        "                    timeout=settings.lookup_executor_handoff_timeout_seconds\n"
        "                )" in source
    )
