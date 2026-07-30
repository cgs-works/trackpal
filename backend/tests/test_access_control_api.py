from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import select

from app.models import BlockedClient, MailLookupJob, Tenant, TenantMailbox
from app.services.whatsapp_session_service import ConversationSession

pytestmark = pytest.mark.asyncio


class _FakeRedis:
    def __init__(self) -> None:
        self.store: dict[str, str] = {}

    async def get(self, key: str) -> str | None:
        return self.store.get(key)

    async def set(
        self, key: str, value: str, ex: int | None = None, keepttl: bool = False
    ) -> None:
        self.store[key] = value

    async def delete(self, key: str) -> int:
        return 1 if self.store.pop(key, None) is not None else 0


class _FakeManager:
    def __init__(self, redis: _FakeRedis) -> None:
        self.redis = redis

    async def execute(self, operation_name: str, async_callable):
        return await async_callable(self.redis)


async def _tenant_headers(client):
    login = await client.post(
        "/api/v1/auth/login", json={"username": "tenant", "password": "tenant-password"}
    )
    assert login.status_code == 200, login.text
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


async def _tenant(db_session, active_tenant_user):
    row = await db_session.execute(
        select(Tenant).where(Tenant.owner_user_id == active_tenant_user.id)
    )
    return row.scalar_one()


async def test_access_control_list_block_duplicate_and_unblock(
    client, db_session, active_tenant_user
):
    headers = await _tenant_headers(client)

    created = await client.post(
        "/api/v1/access-control/blocks", json={"phone": "+12015550222"}, headers=headers
    )
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["phone"] == "12015550222"
    assert "is_active" not in body

    tenant = await _tenant(db_session, active_tenant_user)
    row = await db_session.get(BlockedClient, uuid.UUID(body["id"]))
    assert row is not None
    assert row.tenant_id == tenant.id

    duplicate = await client.post(
        "/api/v1/access-control/blocks", json={"phone": "+12015550222"}, headers=headers
    )
    assert duplicate.status_code == 409

    listed = await client.get("/api/v1/access-control/blocks", headers=headers)
    assert listed.status_code == 200, listed.text
    assert [row["phone"] for row in listed.json()] == ["12015550222"]
    assert "is_active" not in listed.json()[0]

    deleted = await client.delete(
        f"/api/v1/access-control/blocks/{body['id']}", headers=headers
    )
    assert deleted.status_code == 204

    listed_again = await client.get("/api/v1/access-control/blocks", headers=headers)
    assert listed_again.status_code == 200
    assert listed_again.json() == []
    # Expire the identity map so db_session.get() re-fetches from DB
    # (the API endpoint commits on a separate session).
    db_session.expire_all()
    assert await db_session.get(BlockedClient, uuid.UUID(body["id"])) is None


async def test_block_phone_cancels_active_codigo_session_and_job(
    client, db_session, active_tenant_user, monkeypatch
):
    from app.services import access_control_service

    tenant = await _tenant(db_session, active_tenant_user)
    mailbox = TenantMailbox(
        tenant_id=tenant.id,
        mailbox_email="codes@example.com",
        auth_method="oauth",
        status="connected",
    )
    db_session.add(mailbox)
    await db_session.flush()
    job = MailLookupJob(
        tenant_id=tenant.id,
        mailbox_id=mailbox.id,
        service_key="netflix",
        target_email="viewer@example.com",
        status="pending",
        expires_at=datetime.now(timezone.utc).replace(year=2099),
    )
    db_session.add(job)
    await db_session.commit()

    redis = _FakeRedis()
    session_key = f"session:unreg:{str(tenant.id)[:8]}:12015550223"
    redis.store[session_key] = ConversationSession(
        phone=f"unreg:{str(tenant.id)[:8]}:12015550223",
        flow="codigo",
        step="awaiting_result",
        temp_data={"lookup_job_id": str(job.id)},
    ).model_dump_json()
    monkeypatch.setattr(
        access_control_service, "get_redis_manager", lambda: _FakeManager(redis)
    )

    headers = await _tenant_headers(client)
    created = await client.post(
        "/api/v1/access-control/blocks", json={"phone": "+12015550223"}, headers=headers
    )
    assert created.status_code == 201, created.text

    assert session_key not in redis.store
    await db_session.refresh(job)
    assert job.status == "failed"
    assert job.error_code == "user_cancelled"
