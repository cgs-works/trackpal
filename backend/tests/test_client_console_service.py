"""Tests for WhatsApp Client Console facade and instance-first routing.

Covers:
- Client console menu flow (profile, subscriptions, exit)
- Instance routing (master instance, tenant instance, unknown)
- Tenant + client ambiguity (mode prompt, persistence, clear)
- Access denial for inactive/unknown clients
- Cross-tenant isolation
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import UUID, uuid4
from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import settings
from app.services.whatsapp_client_console_facade import WhatsAppClientConsoleFacade
from app.services.whatsapp_session_service import (
    ConversationSession,
    WhatsAppSessionService,
)
from app.main import app


@pytest.fixture(autouse=True)
def _force_spanish_locale(monkeypatch: pytest.MonkeyPatch) -> None:
    """Force locale to ``"es"`` for all client-console integration tests.

    The ``active_tenant_user`` fixture creates a tenant with ``locale="en"``
    (the model default), but these tests were written with hardcoded Spanish
    strings. When the texts were migrated to i18n we need the Spanish variant
    to keep the existing assertions passing.
    """
    monkeypatch.setattr(
        "app.api.v1.endpoints.integrations.console._tl",
        lambda _tenant: "es",
    )


pytestmark = pytest.mark.asyncio

ENDPOINT = "/api/v1/integrations/n8n/console"

# ===================================================================
# Fakes (same pattern as test_tenant_console_service.py)
# ===================================================================


class FakeRedis:
    """Minimal in-memory fake for redis.asyncio.Redis."""

    def __init__(self) -> None:
        self._store: dict[str, str] = {}

    async def get(self, key: str) -> str | None:
        return self._store.get(key)

    async def set(
        self, key: str, value: str, ex: int | None = None, keepttl: bool = False
    ) -> None:
        self._store[key] = value

    async def delete(self, key: str) -> int:
        return 1 if self._store.pop(key, None) is not None else 0

    async def exists(self, key: str) -> int:
        return 1 if key in self._store else 0

    async def expire(self, key: str, time: int) -> int:
        if key in self._store:
            return 1
        return 0


class FakeManager:
    """Duck-typed connection manager that delegates execute() to FakeRedis."""

    def __init__(self, fake_redis: FakeRedis | None = None) -> None:
        self._redis = fake_redis or FakeRedis()

    async def execute(self, operation_name: str, async_callable: Any) -> Any:
        return await async_callable(self._redis)


# ===================================================================
# Fixtures
# ===================================================================


@pytest.fixture
def fake_redis() -> FakeRedis:
    return FakeRedis()


@pytest.fixture
def session_service(fake_redis: FakeRedis) -> WhatsAppSessionService:
    return WhatsAppSessionService(
        connection_manager=FakeManager(fake_redis=fake_redis),
        ttl_seconds=900,
    )


@pytest.fixture
def client_facade(
    session_service: WhatsAppSessionService,
) -> WhatsAppClientConsoleFacade:
    return WhatsAppClientConsoleFacade(
        session_service=session_service,
    )


def _client_identity(
    client_id: UUID | None = None, tenant_id: UUID | None = None
) -> dict[str, Any]:
    """Build a client identity dict matching what console.py constructs."""
    return {
        "user_id": str(uuid4()),
        "role": "client",
        "username": "client_test",
        "client_id": str(client_id or uuid4()),
        "tenant_id": str(tenant_id or uuid4()),
    }


# ===================================================================
# Client Console Facade — menu flow
# ===================================================================


@pytest.mark.asyncio
class TestClientConsoleMenu:
    """Client console main menu, profile, subscriptions, exit."""

    async def test_main_menu_empty_message(
        self, client_facade: WhatsAppClientConsoleFacade
    ) -> None:
        """Empty message returns main menu."""
        identity = _client_identity()
        reply = await client_facade.process_message(
            phone="+10000000000",
            message="",
            identity=identity,
        )
        assert "Consola de Cliente" in reply
        assert "Ver mi perfil" in reply
        assert "Ver suscripciones activas" in reply
        assert "Salir" in reply

    async def test_main_menu_menu_command(
        self, client_facade: WhatsAppClientConsoleFacade
    ) -> None:
        """'menu' command returns main menu."""
        identity = _client_identity()
        reply = await client_facade.process_message(
            phone="+10000000000",
            message="menu",
            identity=identity,
        )
        assert "Consola de Cliente" in reply

    async def test_option_1_profile_no_db(
        self, client_facade: WhatsAppClientConsoleFacade
    ) -> None:
        """Option 1 without db returns error."""
        identity = _client_identity()
        reply = await client_facade.process_message(
            phone="+10000000000",
            message="1",
            identity=identity,
        )
        assert "Error interno" in reply

    async def test_option_2_subscriptions_no_db(
        self, client_facade: WhatsAppClientConsoleFacade
    ) -> None:
        """Option 2 without db returns error."""
        identity = _client_identity()
        reply = await client_facade.process_message(
            phone="+10000000000",
            message="2",
            identity=identity,
        )
        assert "Error interno" in reply

    async def test_option_0_exit(
        self,
        client_facade: WhatsAppClientConsoleFacade,
        session_service: WhatsAppSessionService,
        fake_redis: FakeRedis,
    ) -> None:
        """Option 0 exits and clears session."""
        # Create a session first
        await session_service.create_session("client:+10000000000")

        identity = _client_identity()
        reply = await client_facade.process_message(
            phone="+10000000000",
            message="0",
            identity=identity,
        )
        assert "salido" in reply.lower()
        # Session should be cleared
        session = await session_service.get_session("client:+10000000000")
        assert session is None

    async def test_invalid_option_falls_to_menu(
        self, client_facade: WhatsAppClientConsoleFacade
    ) -> None:
        """Invalid input returns main menu."""
        identity = _client_identity()
        reply = await client_facade.process_message(
            phone="+10000000000",
            message="99",
            identity=identity,
        )
        assert "Consola de Cliente" in reply

    async def test_unknown_phone_cannot_use_master_instance(
        self,
        monkeypatch: pytest.MonkeyPatch,
        db_session: Any,
        client: AsyncClient,
    ) -> None:
        """Unknown phone on MASTER_WHATSAPP_INSTANCE returns no-access."""
        monkeypatch.setattr(
            "app.core.config.settings.master_whatsapp_instance",
            "master-instance",
        )

        fake_mgr = FakeManager()
        with patch(
            "app.api.v1.endpoints.integrations.console.get_redis_manager",
            return_value=fake_mgr,
        ):
            response = await client.post(
                ENDPOINT,
                json={
                    "phone": "+9999999999",
                    "message": "hola",
                    "instance": "master-instance",
                },
                headers={"X-API-Key": settings.n8n_api_key},
            )
        assert response.status_code == 200
        reply = response.json()["reply"].lower()
        assert "no tienes acceso" in reply or "no está registrado" in reply


# ===================================================================
# Instance-first routing
# ===================================================================


@pytest.mark.asyncio
class TestInstanceFirstRouting:
    """Instance-first routing: master vs tenant vs unknown."""

    async def test_master_instance_routes_only_master(
        self,
        monkeypatch: pytest.MonkeyPatch,
        client: AsyncClient,
        master_user: Any,
    ) -> None:
        """Master instance + master phone → master console."""
        monkeypatch.setattr(
            "app.core.config.settings.master_whatsapp_instance",
            "master-instance",
        )

        fake_mgr = FakeManager()
        from datetime import datetime, timezone
        from app.services.whatsapp_auth_session_service import WhatsAppAuthSession

        auth_session = WhatsAppAuthSession(
            phone="12015550001",
            user_id=str(master_user.id),
            username=master_user.username,
            role="master",
            authenticated_at=datetime.now(timezone.utc),
        )
        await fake_mgr._redis.set(
            "wa:auth:12015550001", auth_session.model_dump_json(), ex=900
        )

        with patch(
            "app.api.v1.endpoints.integrations.console.get_redis_manager",
            return_value=fake_mgr,
        ):
            response = await client.post(
                ENDPOINT,
                json={
                    "phone": "+12015550001",
                    "message": "menu",
                    "instance": "master-instance",
                },
                headers={"X-API-Key": settings.n8n_api_key},
            )
        assert response.status_code == 200
        reply = response.json()["reply"]
        assert "Master Console" in reply or "Trackpal" in reply

    async def test_master_instance_rejects_tenant_phone(
        self,
        monkeypatch: pytest.MonkeyPatch,
        client: AsyncClient,
        active_tenant_user: Any,
    ) -> None:
        """Master instance + tenant phone → no-access (only master on this instance)."""
        monkeypatch.setattr(
            "app.core.config.settings.master_whatsapp_instance",
            "master-instance",
        )

        fake_mgr = FakeManager()
        with patch(
            "app.api.v1.endpoints.integrations.console.get_redis_manager",
            return_value=fake_mgr,
        ):
            response = await client.post(
                ENDPOINT,
                json={
                    "phone": "+12015550002",
                    "message": "hola",
                    "instance": "master-instance",
                },
                headers={"X-API-Key": settings.n8n_api_key},
            )
        assert response.status_code == 200
        reply = response.json()["reply"].lower()
        assert "no tienes acceso" in reply or "no está registrado" in reply

    async def test_tenant_instance_resolves_tenant(
        self,
        monkeypatch: pytest.MonkeyPatch,
        client: AsyncClient,
        active_tenant_user: Any,
        db_session: Any,
    ) -> None:
        """Tenant instance + tenant admin phone → tenant console."""
        # Set the tenant's evolution_instance_name
        from sqlalchemy import select
        from app.models import Tenant as TenantModel

        result = await db_session.execute(
            select(TenantModel).where(
                TenantModel.owner_user_id == active_tenant_user.id
            )
        )
        tenant = result.scalar_one()
        tenant.evolution_instance_name = "tenant-instance-test"
        await db_session.commit()

        fake_mgr = FakeManager()

        with patch(
            "app.api.v1.endpoints.integrations.console.get_redis_manager",
            return_value=fake_mgr,
        ):
            response = await client.post(
                ENDPOINT,
                json={
                    "phone": "+12015550002",
                    "message": "",
                    "instance": "tenant-instance-test",
                },
                headers={"X-API-Key": settings.n8n_api_key},
            )
        assert response.status_code == 200
        reply = response.json()["reply"]
        assert "Consola de Administración" in reply or "Trackpal" in reply

    async def test_unknown_instance_falls_back_to_legacy(
        self,
        client: AsyncClient,
        master_user: Any,
    ) -> None:
        """Unknown instance with no tenant match → legacy phone identification."""
        from datetime import datetime, timezone
        from app.services.whatsapp_auth_session_service import WhatsAppAuthSession

        fake_mgr = FakeManager()
        auth_session = WhatsAppAuthSession(
            phone="12015550001",
            user_id=str(master_user.id),
            username=master_user.username,
            role="master",
            authenticated_at=datetime.now(timezone.utc),
        )
        await fake_mgr._redis.set(
            "wa:auth:12015550001", auth_session.model_dump_json(), ex=900
        )

        with patch(
            "app.api.v1.endpoints.integrations.console.get_redis_manager",
            return_value=fake_mgr,
        ):
            response = await client.post(
                ENDPOINT,
                json={
                    "phone": "+12015550001",
                    "message": "menu",
                    "instance": "nonexistent-instance",
                },
                headers={"X-API-Key": settings.n8n_api_key},
            )
        assert response.status_code == 200
        reply = response.json()["reply"]
        # Should fall back to legacy master flow
        assert "Master Console" in reply or "Trackpal" in reply


# ===================================================================
# Client resolution within tenant
# ===================================================================


@pytest.mark.asyncio
class TestClientWithinTenant:
    """Client identity resolution by (tenant_id, phone) via instance."""

    async def test_client_phone_in_tenant_instance(
        self,
        client: AsyncClient,
        active_client_user: Any,
        active_tenant_user: Any,
        db_session: Any,
    ) -> None:
        """Client phone + matching tenant instance → client console."""
        # Set the tenant's evolution_instance_name
        from sqlalchemy import select
        from app.models import Tenant as TenantModel

        result = await db_session.execute(
            select(TenantModel).where(
                TenantModel.owner_user_id == active_tenant_user.id
            )
        )
        tenant = result.scalar()
        tenant.evolution_instance_name = "tenant-client-test"
        await db_session.commit()

        fake_mgr = FakeManager()

        with patch(
            "app.api.v1.endpoints.integrations.console.get_redis_manager",
            return_value=fake_mgr,
        ):
            response = await client.post(
                ENDPOINT,
                json={
                    "phone": "+12015550030",
                    "message": "",
                    "instance": "tenant-client-test",
                },
                headers={"X-API-Key": settings.n8n_api_key},
            )
        assert response.status_code == 200
        reply = response.json()["reply"]
        assert "Consola de Cliente" in reply
        assert "Ver mi perfil" in reply

    async def test_unknown_client_phone_in_tenant_instance(
        self,
        client: AsyncClient,
        active_tenant_user: Any,
        db_session: Any,
    ) -> None:
        """Unknown phone in tenant instance → access denied."""
        from sqlalchemy import select
        from app.models import Tenant as TenantModel

        result = await db_session.execute(
            select(TenantModel).where(
                TenantModel.owner_user_id == active_tenant_user.id
            )
        )
        tenant = result.scalar()
        tenant.evolution_instance_name = "tenant-deny-test"
        await db_session.commit()

        fake_mgr = FakeManager()

        with patch(
            "app.api.v1.endpoints.integrations.console.get_redis_manager",
            return_value=fake_mgr,
        ):
            response = await client.post(
                ENDPOINT,
                json={
                    "phone": "+9999999999",
                    "message": "hola",
                    "instance": "tenant-deny-test",
                },
                headers={"X-API-Key": settings.n8n_api_key},
            )
        assert response.status_code == 200
        reply = response.json()["reply"]
        assert "no tienes una cuenta activa" in reply

    async def test_inactive_client_in_tenant_instance(
        self,
        client: AsyncClient,
        inactive_client_user: Any,
        active_tenant_user: Any,
        db_session: Any,
    ) -> None:
        """Inactive client phone in tenant instance → access denied."""
        from sqlalchemy import select
        from app.models import Tenant as TenantModel

        result = await db_session.execute(
            select(TenantModel).where(
                TenantModel.owner_user_id == active_tenant_user.id
            )
        )
        tenant = result.scalar()
        tenant.evolution_instance_name = "tenant-inactive-test"
        await db_session.commit()

        fake_mgr = FakeManager()

        with patch(
            "app.api.v1.endpoints.integrations.console.get_redis_manager",
            return_value=fake_mgr,
        ):
            response = await client.post(
                ENDPOINT,
                json={
                    "phone": "+12015550031",
                    "message": "hola",
                    "instance": "tenant-inactive-test",
                },
                headers={"X-API-Key": settings.n8n_api_key},
            )
        assert response.status_code == 200
        reply = response.json()["reply"]
        assert "no tienes una cuenta activa" in reply

    async def test_cross_tenant_client_isolated(
        self,
        client: AsyncClient,
        db_session: Any,
        active_client_user: Any,
    ) -> None:
        """Client from tenant A cannot access tenant B via its instance.

        Creates two tenants with different instances, registers the client
        only in tenant A, then verifies that accessing tenant B's instance
        with the same phone returns access denied.
        """
        from app.core.security import get_password_hash
        from app.models import (
            Client as ClientModel,
            Tenant as TenantModel,
            User as UserModel,
        )

        # Tenant A (fixture gives us active_client_user under active_tenant_user)
        from sqlalchemy import select

        result = await db_session.execute(
            select(TenantModel).where(
                TenantModel.owner_user_id == active_client_user.id
            )
        )
        tenant_a = result.scalar_one_or_none()
        # Actually active_client_user is under active_tenant_user's tenant.
        # Let's find tenant A from the client's tenant_id
        client_obj = await db_session.execute(
            select(ClientModel).where(
                ClientModel.owner_user_id == active_client_user.id
            )
        )
        client_obj = client_obj.scalar_one()
        result = await db_session.execute(
            select(TenantModel).where(TenantModel.id == client_obj.tenant_id)
        )
        tenant_a = result.scalar_one()
        tenant_a.evolution_instance_name = "tenant-a-instance"

        # Create Tenant B with different instance
        user_b = UserModel(
            username="tenant-b",
            password_hash=get_password_hash("pass"),
            role="tenant",
        )
        db_session.add(user_b)
        await db_session.flush()
        tenant_b = TenantModel(
            owner_user_id=user_b.id,
            client_prefix="tnb99",
            name="Tenant B",
            whatsapp_phone=None,
            evolution_instance_name="tenant-b-instance",
            is_active=True,
        )
        db_session.add(tenant_b)
        await db_session.commit()

        # Phone +12015550030 belongs to a client in tenant A, NOT tenant B
        fake_mgr = FakeManager()
        with patch(
            "app.api.v1.endpoints.integrations.console.get_redis_manager",
            return_value=fake_mgr,
        ):
            response = await client.post(
                ENDPOINT,
                json={
                    "phone": "+12015550030",
                    "message": "hola",
                    "instance": "tenant-b-instance",
                },
                headers={"X-API-Key": settings.n8n_api_key},
            )
        assert response.status_code == 200
        reply = response.json()["reply"]
        # Client from tenant A not found in tenant B → access denied
        assert "no tienes una cuenta activa" in reply


# ===================================================================
# Ambiguity: tenant admin + client same phone
# ===================================================================


@pytest.mark.asyncio
class TestAmbiguity:
    """Phone matches both tenant admin and client in same instance."""

    async def test_ambiguity_prompts_mode(
        self,
        client: AsyncClient,
        active_tenant_user: Any,
        db_session: Any,
    ) -> None:
        """Both tenant admin + client match → mode prompt."""
        from sqlalchemy import select
        from app.models import Client as ClientModel, Tenant as TenantModel

        # Set tenant instance
        result = await db_session.execute(
            select(TenantModel).where(
                TenantModel.owner_user_id == active_tenant_user.id
            )
        )
        tenant = result.scalar()
        tenant.evolution_instance_name = "tenant-ambiguity-test"
        await db_session.commit()

        # Create a client WITH the same phone as the tenant admin
        client_model = ClientModel(
            tenant_id=tenant.id,
            owner_user_id=active_tenant_user.id,
            full_name="Same Phone Client",
            username=f"{tenant.client_prefix}_samephone",
            phone="+12015550002",  # Same as tenant admin
            is_active=True,
        )
        db_session.add(client_model)
        await db_session.commit()

        fake_mgr = FakeManager()
        with patch(
            "app.api.v1.endpoints.integrations.console.get_redis_manager",
            return_value=fake_mgr,
        ):
            response = await client.post(
                ENDPOINT,
                json={
                    "phone": "+12015550002",
                    "message": "hola",
                    "instance": "tenant-ambiguity-test",
                },
                headers={"X-API-Key": settings.n8n_api_key},
            )
        assert response.status_code == 200
        reply = response.json()["reply"]
        assert "dos perfiles" in reply or "cómo quieres proceder" in reply

    async def test_ambiguity_select_client_mode(
        self,
        client: AsyncClient,
        active_tenant_user: Any,
        db_session: Any,
    ) -> None:
        """After ambiguity prompt, selecting client mode persists and confirms."""
        from sqlalchemy import select
        from app.models import Client as ClientModel, Tenant as TenantModel

        result = await db_session.execute(
            select(TenantModel).where(
                TenantModel.owner_user_id == active_tenant_user.id
            )
        )
        tenant = result.scalar()
        tenant.evolution_instance_name = "tenant-ambig-client"
        await db_session.commit()

        # Client with same phone as tenant admin
        db_session.add(
            ClientModel(
                tenant_id=tenant.id,
                owner_user_id=active_tenant_user.id,
                full_name="Ambiguous Client",
                username=f"{tenant.client_prefix}_ambig",
                phone="+12015550002",
                is_active=True,
            )
        )
        await db_session.commit()

        fake_mgr = FakeManager()
        with patch(
            "app.api.v1.endpoints.integrations.console.get_redis_manager",
            return_value=fake_mgr,
        ):
            # First message triggers prompt
            await client.post(
                ENDPOINT,
                json={
                    "phone": "+12015550002",
                    "message": "hola",
                    "instance": "tenant-ambig-client",
                },
                headers={"X-API-Key": settings.n8n_api_key},
            )
            # Second message selects client mode
            response = await client.post(
                ENDPOINT,
                json={
                    "phone": "+12015550002",
                    "message": "2",
                    "instance": "tenant-ambig-client",
                },
                headers={"X-API-Key": settings.n8n_api_key},
            )
        assert response.status_code == 200
        reply = response.json()["reply"]
        assert "modo *Cliente*" in reply

    async def test_ambiguity_select_tenant_mode(
        self,
        client: AsyncClient,
        active_tenant_user: Any,
        db_session: Any,
    ) -> None:
        """After ambiguity prompt, selecting tenant mode persists and confirms."""
        from sqlalchemy import select
        from app.models import Client as ClientModel, Tenant as TenantModel

        result = await db_session.execute(
            select(TenantModel).where(
                TenantModel.owner_user_id == active_tenant_user.id
            )
        )
        tenant = result.scalar()
        tenant.evolution_instance_name = "tenant-ambig-tenant"
        await db_session.commit()

        db_session.add(
            ClientModel(
                tenant_id=tenant.id,
                owner_user_id=active_tenant_user.id,
                full_name="Another Client",
                username=f"{tenant.client_prefix}_another",
                phone="+12015550002",
                is_active=True,
            )
        )
        await db_session.commit()

        fake_mgr = FakeManager()
        with patch(
            "app.api.v1.endpoints.integrations.console.get_redis_manager",
            return_value=fake_mgr,
        ):
            await client.post(
                ENDPOINT,
                json={
                    "phone": "+12015550002",
                    "message": "hola",
                    "instance": "tenant-ambig-tenant",
                },
                headers={"X-API-Key": settings.n8n_api_key},
            )
            response = await client.post(
                ENDPOINT,
                json={
                    "phone": "+12015550002",
                    "message": "1",
                    "instance": "tenant-ambig-tenant",
                },
                headers={"X-API-Key": settings.n8n_api_key},
            )
        assert response.status_code == 200
        reply = response.json()["reply"]
        assert "modo *Administrador de tenant*" in reply

    async def test_ambiguity_mode_persists_messages(
        self,
        client: AsyncClient,
        active_tenant_user: Any,
        db_session: Any,
    ) -> None:
        """After selecting client mode, subsequent messages remain in client console."""
        from sqlalchemy import select
        from app.models import Client as ClientModel, Tenant as TenantModel

        result = await db_session.execute(
            select(TenantModel).where(
                TenantModel.owner_user_id == active_tenant_user.id
            )
        )
        tenant = result.scalar()
        tenant.evolution_instance_name = "tenant-ambig-persist"
        await db_session.commit()

        db_session.add(
            ClientModel(
                tenant_id=tenant.id,
                owner_user_id=active_tenant_user.id,
                full_name="Persist Client",
                username=f"{tenant.client_prefix}_persist",
                phone="+12015550002",
                is_active=True,
            )
        )
        await db_session.commit()

        fake_mgr = FakeManager()
        with patch(
            "app.api.v1.endpoints.integrations.console.get_redis_manager",
            return_value=fake_mgr,
        ):
            # Trigger ambiguity
            await client.post(
                ENDPOINT,
                json={
                    "phone": "+12015550002",
                    "message": "hola",
                    "instance": "tenant-ambig-persist",
                },
                headers={"X-API-Key": settings.n8n_api_key},
            )
            # Select client mode
            await client.post(
                ENDPOINT,
                json={
                    "phone": "+12015550002",
                    "message": "2",
                    "instance": "tenant-ambig-persist",
                },
                headers={"X-API-Key": settings.n8n_api_key},
            )
            # Next message should be in client console (no re-prompt)
            response = await client.post(
                ENDPOINT,
                json={
                    "phone": "+12015550002",
                    "message": "",
                    "instance": "tenant-ambig-persist",
                },
                headers={"X-API-Key": settings.n8n_api_key},
            )
        assert response.status_code == 200
        reply = response.json()["reply"]
        assert "Consola de Cliente" in reply

    async def test_ambiguity_zero_exits_and_clears_mode(
        self,
        client: AsyncClient,
        active_tenant_user: Any,
        db_session: Any,
    ) -> None:
        """Selecting client mode then '0' exits and clears mode."""
        from sqlalchemy import select
        from app.models import Client as ClientModel, Tenant as TenantModel

        result = await db_session.execute(
            select(TenantModel).where(
                TenantModel.owner_user_id == active_tenant_user.id
            )
        )
        tenant = result.scalar()
        tenant.evolution_instance_name = "tenant-ambig-exit"
        await db_session.commit()

        db_session.add(
            ClientModel(
                tenant_id=tenant.id,
                owner_user_id=active_tenant_user.id,
                full_name="Exit Client",
                username=f"{tenant.client_prefix}_exit",
                phone="+12015550002",
                is_active=True,
            )
        )
        await db_session.commit()

        fake_mgr = FakeManager()
        with patch(
            "app.api.v1.endpoints.integrations.console.get_redis_manager",
            return_value=fake_mgr,
        ):
            # Trigger ambiguity
            await client.post(
                ENDPOINT,
                json={
                    "phone": "+12015550002",
                    "message": "hola",
                    "instance": "tenant-ambig-exit",
                },
                headers={"X-API-Key": settings.n8n_api_key},
            )
            # Select client mode
            await client.post(
                ENDPOINT,
                json={
                    "phone": "+12015550002",
                    "message": "2",
                    "instance": "tenant-ambig-exit",
                },
                headers={"X-API-Key": settings.n8n_api_key},
            )
            # Send 0 to exit — should clear session and mode
            response = await client.post(
                ENDPOINT,
                json={
                    "phone": "+12015550002",
                    "message": "0",
                    "instance": "tenant-ambig-exit",
                },
                headers={"X-API-Key": settings.n8n_api_key},
            )
        assert response.status_code == 200
        reply = response.json()["reply"]
        assert "salido" in reply.lower()

        # Mode key should be removed — next message should re-prompt
        mode_key = f"wa:mode:12015550002"
        raw = await fake_mgr._redis.get(mode_key)
        assert raw is None

        # Conversation sessions should also be cleared
        from app.services.whatsapp_session_service import ConversationSession

        admin_key = "session:admin:12015550002"
        client_key = "session:client:12015550002"
        assert await fake_mgr._redis.get(admin_key) is None
        assert await fake_mgr._redis.get(client_key) is None


# ===================================================================
# Duplicate phone within same tenant
# ===================================================================


@pytest.mark.asyncio
class TestDuplicatePhone:
    """Hard-fail when duplicate client phones exist in same tenant."""

    async def test_duplicate_client_phone_returns_support_message(
        self,
        client: AsyncClient,
        active_tenant_user: Any,
        db_session: Any,
    ) -> None:
        """Legacy duplicate phone data → support message, not 500.

        The DB schema enforces unique (tenant_id, phone), so duplicates
        can't happen in practice. This test simulates the scenario via
        a mocked repository to verify the hard-fail handling.
        """
        from unittest.mock import AsyncMock
        from sqlalchemy.exc import MultipleResultsFound

        from sqlalchemy import select
        from app.models import Tenant as TenantModel

        result = await db_session.execute(
            select(TenantModel).where(
                TenantModel.owner_user_id == active_tenant_user.id
            )
        )
        tenant = result.scalar()
        tenant.evolution_instance_name = "tenant-dup-test"
        await db_session.commit()

        # Mock the repository to raise MultipleResultsFound
        async def _mock_duplicate(*args: Any, **kwargs: Any) -> None:
            raise MultipleResultsFound("Multiple rows found")

        fake_mgr = FakeManager()
        with patch(
            "app.repositories.clients_repository.get_active_client_by_tenant_phone",
            _mock_duplicate,
        ):
            with patch(
                "app.api.v1.endpoints.integrations.console.get_redis_manager",
                return_value=fake_mgr,
            ):
                response = await client.post(
                    ENDPOINT,
                    json={
                        "phone": "+12015550030",
                        "message": "hola",
                        "instance": "tenant-dup-test",
                    },
                    headers={"X-API-Key": settings.n8n_api_key},
                )
        assert response.status_code == 200
        reply = response.json()["reply"]
        assert "Múltiples registros" in reply or "soporte" in reply


# ===================================================================
# Legacy master/tenant flow with instance fallback
# ===================================================================


@pytest.mark.asyncio
class TestLegacyFlowWithInstance:
    """Existing master/tenant console works when instance doesn't match."""

    async def test_tenant_phone_unknown_instance_falls_back_to_tenant_console(
        self,
        client: AsyncClient,
        active_tenant_user: Any,
    ) -> None:
        """Tenant phone + unknown instance → legacy tenant console."""
        fake_mgr = FakeManager()
        with patch(
            "app.api.v1.endpoints.integrations.console.get_redis_manager",
            return_value=fake_mgr,
        ):
            response = await client.post(
                ENDPOINT,
                json={
                    "phone": "+12015550002",
                    "message": "hola",
                    "instance": "unknown-instance-xyz",
                },
                headers={"X-API-Key": settings.n8n_api_key},
            )
        assert response.status_code == 200
        reply = response.json()["reply"]
        # Tenant should get routed to tenant console via legacy fallback
        assert "didn't understand" in reply or "Consola de Administración" in reply
