from __future__ import annotations

from typing import Any
from unittest.mock import patch

import pytest
from sqlalchemy import select

from app.core.config import settings
from app.models import Tenant

pytestmark = pytest.mark.asyncio

ENDPOINT = "/api/v1/integrations/n8n/console"


class _FakeRedis:
    def __init__(self) -> None:
        self._store: dict[str, str] = {}
        self._ttls: dict[str, int] = {}

    async def get(self, key: str) -> str | None:
        return self._store.get(key)

    async def set(
        self, key: str, value: str, ex: int | None = None, keepttl: bool = False
    ) -> None:
        self._store[key] = value
        if ex is not None:
            self._ttls[key] = ex
        elif not keepttl:
            self._ttls.pop(key, None)

    async def expire(self, key: str, time: int) -> int:
        if key in self._store:
            self._ttls[key] = time
            return 1
        return 0

    async def delete(self, key: str) -> int:
        self._ttls.pop(key, None)
        return 1 if self._store.pop(key, None) is not None else 0


class _FakeManager:
    def __init__(self) -> None:
        self._redis = _FakeRedis()

    @property
    def used_backup(self) -> bool:
        return False

    async def execute(self, operation_name: str, async_callable: Any):
        return await async_callable(self._redis)


async def test_instance_alias_with_tenant_prefix_routes_tenant(
    client, active_tenant_user, db_session
):
    result = await db_session.execute(
        select(Tenant).where(Tenant.owner_user_id == active_tenant_user.id)
    )
    tenant = result.scalar_one()
    tenant.evolution_instance_name = "alias-instance"
    await db_session.commit()

    fake_mgr = _FakeManager()
    with patch(
        "app.api.v1.endpoints.integrations.console.get_redis_manager",
        return_value=fake_mgr,
    ):
        response = await client.post(
            ENDPOINT,
            json={
                "phone": "+12015550002",
                "message": "",
                "instance": "tenant-alias-instance",
            },
            headers={"X-API-Key": settings.n8n_api_key},
        )

    assert response.status_code == 200
    reply = response.json()["reply"]
    assert "Consola de Administración" in reply or "TrackPal" in reply
