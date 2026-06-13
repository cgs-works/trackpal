from unittest.mock import patch

import pytest
from sqlalchemy import select

from app.core.config import settings
from app.models import (
    Client,
    CodeServiceGlobalStatus,
    Tenant,
    TenantCodeServiceSelection,
    TenantMailbox,
    TenantSettings,
    User,
)

pytestmark = pytest.mark.asyncio

ENDPOINT = "/api/v1/integrations/n8n/console"
TEST_INSTANCE = "test-tenant-instance"


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

    async def lpush(self, key: str, value: str) -> int:
        self._store[key] = value
        return 1


class _FakeManager:
    def __init__(
        self, *, used_backup: bool = False, fail_on_execute: bool = False
    ) -> None:
        from app.core.redis_client import RedisUnavailableError

        self._redis = _FakeRedis()
        self._used_backup = used_backup
        self._fail_on_execute = fail_on_execute
        self._RedisUnavailableError = RedisUnavailableError

    @property
    def used_backup(self) -> bool:
        return self._used_backup

    async def execute(self, operation_name: str, async_callable):
        if self._fail_on_execute:
            raise self._RedisUnavailableError("Both Redis stores unavailable")
        return await async_callable(self._redis)


async def _setup_tenant_with_instance(db_session, active_tenant_user) -> Tenant:
    result = await db_session.execute(
        select(Tenant).where(Tenant.owner_user_id == active_tenant_user.id)
    )
    tenant = result.scalar_one_or_none()
    assert tenant is not None
    tenant.evolution_instance_name = TEST_INSTANCE
    ts_result = await db_session.execute(
        select(TenantSettings).where(TenantSettings.tenant_id == tenant.id)
    )
    ts = ts_result.scalar_one()
    ts.locale = "es"
    await db_session.commit()
    return tenant


async def _setup_tenant_for_codigo(db_session, active_tenant_user) -> Tenant:
    tenant = await _setup_tenant_with_instance(db_session, active_tenant_user)

    db_session.add(
        TenantMailbox(
            tenant_id=tenant.id,
            mailbox_email="tech@example.com",
            provider="imap",
            auth_method="password",
            status="connected",
        )
    )
    db_session.add(CodeServiceGlobalStatus(service_key="netflix", is_active=True))
    db_session.add(
        TenantCodeServiceSelection(tenant_id=tenant.id, service_key="netflix")
    )
    await db_session.commit()
    return tenant


async def _create_other_active_tenant(
    db_session,
    *,
    username: str = "other-tenant",
    client_prefix: str = "tnb01",
    phone: str = "+12015550003",
    whatsapp_lid: str | None = None,
) -> Tenant:
    other_user = User(username=username, password_hash="x", role="tenant")
    db_session.add(other_user)
    await db_session.flush()

    other_tenant = Tenant(
        owner_user_id=other_user.id,
        client_prefix=client_prefix,
        name="Other Active Tenant",
        whatsapp_phone=phone,
        whatsapp_lid=whatsapp_lid,
        is_active=True,
        evolution_instance_name="other-instance",
    )
    db_session.add(other_tenant)
    await db_session.commit()
    return other_tenant


async def test_external_tenant_admin_menu_is_silenced_and_closed(
    client, db_session, active_tenant_user
):
    await _setup_tenant_with_instance(db_session, active_tenant_user)
    await _create_other_active_tenant(db_session)

    fake_mgr = _FakeManager(used_backup=False)
    with patch(
        "app.api.v1.endpoints.integrations.console.get_redis_manager",
        return_value=fake_mgr,
    ):
        response = await client.post(
            ENDPOINT,
            json={
                "phone": "+12015550003",
                "message": "/menu",
                "instance": TEST_INSTANCE,
            },
            headers={"X-API-Key": settings.n8n_api_key},
        )

    assert response.status_code == 200
    body = response.json()
    assert body == {
        "reply": "",
        "no_reply": True,
        "status": "closed",
        "close_jid": "12015550003@s.whatsapp.net",
    }


async def test_external_tenant_admin_code_still_reaches_unauthenticated_codigo(
    client, db_session, active_tenant_user
):
    await _setup_tenant_for_codigo(db_session, active_tenant_user)
    await _create_other_active_tenant(db_session)

    fake_mgr = _FakeManager(used_backup=False)
    with patch(
        "app.api.v1.endpoints.integrations.console.get_redis_manager",
        return_value=fake_mgr,
    ):
        response = await client.post(
            ENDPOINT,
            json={
                "phone": "+12015550003",
                "message": "code",
                "instance": TEST_INSTANCE,
            },
            headers={"X-API-Key": settings.n8n_api_key},
        )

    assert response.status_code == 200
    body = response.json()
    assert body.get("no_reply") is not True
    assert "Netflix" in body["reply"]


async def test_external_tenant_admin_menu_is_not_silenced_when_sender_is_active_client(
    client, db_session, active_tenant_user
):
    tenant = await _setup_tenant_with_instance(db_session, active_tenant_user)
    await _create_other_active_tenant(db_session)

    client_user = User(username="dual-role-client", password_hash="x", role="client")
    db_session.add(client_user)
    await db_session.flush()
    db_session.add(
        Client(
            tenant_id=tenant.id,
            owner_user_id=client_user.id,
            full_name="Dual Role Client",
            username=f"{tenant.client_prefix}_dualrole",
            phone="+12015550003",
            is_active=True,
        )
    )
    await db_session.commit()

    fake_mgr = _FakeManager(used_backup=False)
    with patch(
        "app.api.v1.endpoints.integrations.console.get_redis_manager",
        return_value=fake_mgr,
    ):
        response = await client.post(
            ENDPOINT,
            json={
                "phone": "+12015550003",
                "message": "/menu",
                "instance": TEST_INSTANCE,
            },
            headers={"X-API-Key": settings.n8n_api_key},
        )

    assert response.status_code == 200
    body = response.json()
    assert body.get("no_reply") is not True
    assert body["reply"]
    assert "no tienes una cuenta registrada" not in body["reply"].lower()


async def test_from_me_menu_uses_tenant_owner_fallback_for_reply_to_when_admin_payload_is_ambiguous(
    client, db_session, active_tenant_user
):
    tenant = await _setup_tenant_with_instance(db_session, active_tenant_user)
    phone_digits = tenant.whatsapp_phone.lstrip("+")
    expected_jid = f"{phone_digits}@s.whatsapp.net"

    fake_mgr = _FakeManager(used_backup=False)
    with patch(
        "app.api.v1.endpoints.integrations.console.get_redis_manager",
        return_value=fake_mgr,
    ):
        response = await client.post(
            ENDPOINT,
            json={
                "phone": "+12015559999",
                "message": "/menu",
                "instance": TEST_INSTANCE,
                "from_me": True,
                "admin_phone": "+12015559999",
                "target_phone": "+12015559999",
                "target_jid": "12015559999@s.whatsapp.net",
            },
            headers={"X-API-Key": settings.n8n_api_key},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["reply_to"] == expected_jid
    assert body["close_jid"] == expected_jid
    assert body["reply"]
    assert (
        "gesti" in body["reply"].lower() or "client management" in body["reply"].lower()
    )
