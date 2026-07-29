"""Tests for public application-level routes."""

import pytest

pytestmark = pytest.mark.asyncio


async def test_root_redirects_to_trackpal_landing(client):
    response = await client.get("/", follow_redirects=False)

    assert response.status_code == 308
    assert response.headers["location"] == "https://trackpal.wilfredocamacho.dev"
