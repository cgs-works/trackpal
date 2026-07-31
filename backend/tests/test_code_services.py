"""Tests for Bug 05 — Code services catalog (global status + tenant selection)."""

from __future__ import annotations

from httpx import AsyncClient
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_password_hash
from app.main import app  # noqa: F401
from app.models import Tenant, User
from app.models.code_service_global_status import CodeServiceGlobalStatus
from app.schemas.code_services import (
    VALID_SERVICE_KEYS,
    TenantCodeServiceUpdateRequest,
)

# ── Fixtures ─────────────────────────────────────────────────────────────


@pytest_asyncio.fixture
async def master_user(db_session: AsyncSession) -> User:
    user = User(
        username="cs_master",
        password_hash=get_password_hash("pass123"),
        role="master",
    )
    db_session.add(user)
    await db_session.flush()
    from app.models import MasterProfile

    db_session.add(MasterProfile(id=user.id, name="CS Master", phone="+19990000001"))
    await db_session.commit()
    return user


@pytest_asyncio.fixture
async def tenant_user(db_session: AsyncSession) -> User:
    user = User(
        username="cs_tenant",
        password_hash=get_password_hash("pass123"),
        role="tenant",
    )
    db_session.add(user)
    await db_session.flush()
    db_session.add(
        Tenant(
            owner_user_id=user.id,
            client_prefix="cst01",
            name="CS Tenant",
            whatsapp_phone="+19990000002",
            is_active=True,
        )
    )
    await db_session.commit()
    return user


@pytest_asyncio.fixture
async def seed_global_services(db_session: AsyncSession) -> None:
    """Seed global status rows for all supported services."""
    for key in VALID_SERVICE_KEYS:
        db_session.add(CodeServiceGlobalStatus(service_key=key, is_active=True))
    await db_session.commit()


@pytest_asyncio.fixture
async def master_headers(client: AsyncClient, master_user: User) -> dict[str, str]:
    resp = await client.post(
        "/api/v1/auth/login",
        json={"username": "cs_master", "password": "pass123"},
    )
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


@pytest_asyncio.fixture
async def tenant_headers(client: AsyncClient, tenant_user: User) -> dict[str, str]:
    resp = await client.post(
        "/api/v1/auth/login",
        json={"username": "cs_tenant", "password": "pass123"},
    )
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


# ── Global status tests ──────────────────────────────────────────────────


class TestGlobalCodeServices:
    """Master can list and toggle global code service status."""

    @pytest.mark.asyncio
    async def test_list_global_requires_master(
        self, client: AsyncClient, tenant_headers: dict
    ):
        resp = await client.get("/api/v1/code-services/global", headers=tenant_headers)
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_list_global_empty(self, client: AsyncClient, master_headers: dict):
        resp = await client.get("/api/v1/code-services/global", headers=master_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "services" in data
        # No seed rows → empty list
        assert len(data["services"]) == 0

    @pytest.mark.asyncio
    async def test_list_global_seeded(
        self, client: AsyncClient, master_headers: dict, seed_global_services
    ):
        resp = await client.get("/api/v1/code-services/global", headers=master_headers)
        assert resp.status_code == 200
        services = resp.json()["services"]
        assert len(services) == len(VALID_SERVICE_KEYS)
        keys = {s["service_key"] for s in services}
        assert keys == VALID_SERVICE_KEYS

    @pytest.mark.asyncio
    async def test_toggle_single_service(
        self, client: AsyncClient, master_headers: dict, seed_global_services
    ):
        resp = await client.put(
            "/api/v1/code-services/global/netflix",
            headers=master_headers,
            json={"is_active": False},
        )
        assert resp.status_code == 200
        assert resp.json()["is_active"] is False
        assert resp.json()["service_key"] == "netflix"

        # Verify it stayed off
        resp = await client.get("/api/v1/code-services/global", headers=master_headers)
        netflix = next(
            s for s in resp.json()["services"] if s["service_key"] == "netflix"
        )
        assert netflix["is_active"] is False

    @pytest.mark.asyncio
    async def test_toggle_invalid_key_returns_400(
        self, client: AsyncClient, master_headers: dict, seed_global_services
    ):
        resp = await client.put(
            "/api/v1/code-services/global/invalid_svc",
            headers=master_headers,
            json={"is_active": True},
        )
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_bulk_update(
        self, client: AsyncClient, master_headers: dict, seed_global_services
    ):
        payload = {
            "services": {
                "netflix": False,
                "spotify": False,
                "disney": True,
                "hbo_max": True,
                "prime_video": True,
                "universal_plus": True,
            }
        }
        resp = await client.put(
            "/api/v1/code-services/global",
            headers=master_headers,
            json=payload,
        )
        assert resp.status_code == 200
        services = {s["service_key"]: s["is_active"] for s in resp.json()["services"]}
        assert services["netflix"] is False
        assert services["spotify"] is False
        assert services["disney"] is True

    @pytest.mark.asyncio
    async def test_bulk_update_invalid_key_returns_400(
        self, client: AsyncClient, master_headers: dict, seed_global_services
    ):
        resp = await client.put(
            "/api/v1/code-services/global",
            headers=master_headers,
            json={"services": {"bad_key": True}},
        )
        assert resp.status_code == 400


# ── Tenant selection tests ───────────────────────────────────────────────


class TestTenantCodeServices:
    """Tenant can view and update their code service selection."""

    async def _get_tenant_id(self, tenant_user: User) -> str:
        # The tenant_user fixture creates a Tenant with owner_user_id = tenant_user.id
        # We need to get it. Since we're in tests, use a known prefix.
        return "00000000-0000-0000-0000-000000000001"  # Will be set by fixture

    @pytest.mark.asyncio
    async def test_get_selection_empty(
        self, client: AsyncClient, tenant_headers: dict, seed_global_services
    ):
        # Tenant has no selections yet → all services listed, none selected
        # Use the /current endpoint which resolves tenant from token
        resp = await client.get(
            "/api/v1/code-services/tenants/current",
            headers=tenant_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "services" in data
        assert len(data["services"]) == len(VALID_SERVICE_KEYS)
        # All should show as globally active (we seeded them)
        for svc in data["services"]:
            assert svc["is_globally_active"] is True

    @pytest.mark.asyncio
    async def test_update_selection(
        self, client: AsyncClient, tenant_headers: dict, seed_global_services
    ):
        resp = await client.put(
            "/api/v1/code-services/tenants/current",
            headers=tenant_headers,
            json={"service_keys": ["netflix", "disney"]},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["services"]) == len(VALID_SERVICE_KEYS)

        # Verify effective list
        resp = await client.get(
            "/api/v1/code-services/tenants/current/effective",
            headers=tenant_headers,
        )
        assert resp.status_code == 200
        effective = resp.json()
        assert "netflix" in effective
        assert "disney" in effective
        assert len(effective) == 2

    @pytest.mark.asyncio
    async def test_full_replace_sync(
        self, client: AsyncClient, tenant_headers: dict, seed_global_services
    ):
        # First selection
        await client.put(
            "/api/v1/code-services/tenants/current",
            headers=tenant_headers,
            json={"service_keys": ["netflix", "disney"]},
        )
        # Full replace with different set
        resp = await client.put(
            "/api/v1/code-services/tenants/current",
            headers=tenant_headers,
            json={"service_keys": ["spotify"]},
        )
        assert resp.status_code == 200

        # Verify only spotify remains
        resp = await client.get(
            "/api/v1/code-services/tenants/current/effective",
            headers=tenant_headers,
        )
        effective = resp.json()
        assert effective == ["spotify"]

    @pytest.mark.asyncio
    async def test_empty_selection(
        self, client: AsyncClient, tenant_headers: dict, seed_global_services
    ):
        await client.put(
            "/api/v1/code-services/tenants/current",
            headers=tenant_headers,
            json={"service_keys": ["netflix"]},
        )
        resp = await client.put(
            "/api/v1/code-services/tenants/current",
            headers=tenant_headers,
            json={"service_keys": []},
        )
        assert resp.status_code == 200
        resp = await client.get(
            "/api/v1/code-services/tenants/current/effective",
            headers=tenant_headers,
        )
        assert resp.json() == []

    @pytest.mark.asyncio
    async def test_invalid_service_key_returns_400(
        self, client: AsyncClient, tenant_headers: dict, seed_global_services
    ):
        resp = await client.put(
            "/api/v1/code-services/tenants/current",
            headers=tenant_headers,
            json={"service_keys": ["netflix", "bad_key"]},
        )
        assert resp.status_code == 400
        assert "Invalid service_key" in resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_effective_excludes_globally_inactive(
        self,
        client: AsyncClient,
        master_headers: dict,
        tenant_headers: dict,
        seed_global_services,
    ):
        # Tenant selects netflix + disney
        await client.put(
            "/api/v1/code-services/tenants/current",
            headers=tenant_headers,
            json={"service_keys": ["netflix", "disney"]},
        )
        # Master deactivates netflix globally
        await client.put(
            "/api/v1/code-services/global/netflix",
            headers=master_headers,
            json={"is_active": False},
        )
        # Effective list should only have disney
        resp = await client.get(
            "/api/v1/code-services/tenants/current/effective",
            headers=tenant_headers,
        )
        effective = resp.json()
        assert effective == ["disney"]

        # Full tenant list preserves selected-but-globally-inactive state for UI
        resp = await client.get(
            "/api/v1/code-services/tenants/current",
            headers=tenant_headers,
        )
        services = {s["service_key"]: s for s in resp.json()["services"]}
        assert services["netflix"]["is_selected"] is True
        assert services["netflix"]["is_globally_active"] is False

    @pytest.mark.asyncio
    async def test_tenant_cannot_access_global_endpoint(
        self, client: AsyncClient, tenant_headers: dict
    ):
        resp = await client.get("/api/v1/code-services/global", headers=tenant_headers)
        assert resp.status_code == 403


# ── Effective list (matrix) ──────────────────────────────────────────────


class TestEffectiveList:
    """Effective = tenant_selected ∩ global_active, sorted A-Z."""

    @pytest.mark.asyncio
    async def test_no_selection_no_effective(
        self, client: AsyncClient, tenant_headers: dict, seed_global_services
    ):
        resp = await client.get(
            "/api/v1/code-services/tenants/current/effective",
            headers=tenant_headers,
        )
        assert resp.status_code == 200
        assert resp.json() == []

    @pytest.mark.asyncio
    async def test_all_selected_all_active(
        self, client: AsyncClient, tenant_headers: dict, seed_global_services
    ):
        all_keys = sorted(VALID_SERVICE_KEYS)
        await client.put(
            "/api/v1/code-services/tenants/current",
            headers=tenant_headers,
            json={"service_keys": all_keys},
        )
        resp = await client.get(
            "/api/v1/code-services/tenants/current/effective",
            headers=tenant_headers,
        )
        assert resp.json() == all_keys

    @pytest.mark.asyncio
    async def test_sorted_alphabetically(
        self, client: AsyncClient, tenant_headers: dict, seed_global_services
    ):
        # Select in reverse order
        await client.put(
            "/api/v1/code-services/tenants/current",
            headers=tenant_headers,
            json={"service_keys": ["universal_plus", "disney", "netflix"]},
        )
        resp = await client.get(
            "/api/v1/code-services/tenants/current/effective",
            headers=tenant_headers,
        )
        assert resp.json() == ["disney", "netflix", "universal_plus"]


# ── Regression: removed trackpal_demo key ──────────────────────────────


def test_removed_trackpal_demo_key_is_invalid() -> None:
    request = TenantCodeServiceUpdateRequest(service_keys=["trackpal_demo"])
    with pytest.raises(ValueError, match="trackpal_demo"):
        request.validate_keys()
