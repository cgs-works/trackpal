"""Tests for WhatsApp Link API endpoints and service orchestration.

These tests cover authentication, authorization, error mapping,
and service-level behaviour for the tenant WhatsApp self-linking flow.
"""

from __future__ import annotations

import uuid
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from app.core.tenant_plan import TENANT_PLAN_PRO, TENANT_PLAN_STARTER
from app.services.evolution_client import EvolutionClientError


# ── Helpers ──────────────────────────────────────────────────────────────────


async def _seed_tenant_with_evolution(
    db_session,
    *,
    plan: str = TENANT_PLAN_PRO,
    is_active: bool = True,
    has_instance_name: bool = True,
    has_instance_token: bool = True,
    has_phone: bool = True,
    phone: str | None = None,
) -> tuple[Any, Any]:
    """Create a tenant user + tenant with optional Evolution config."""
    from app.core.security import get_password_hash
    from app.models import Tenant, TenantSettings, User

    suffix = uuid.uuid4().hex[:8]
    user = User(
        username=f"wl_tenant_{suffix}",
        password_hash=get_password_hash("pass"),
        role="tenant",
    )
    db_session.add(user)
    await db_session.flush()

    instance_name = f"inst-{suffix}" if has_instance_name else None
    instance_token = f"encrypted-token-{suffix}" if has_instance_token else None
    whatsapp_phone = (
        phone if phone is not None else (f"+1555{suffix[-8:]}" if has_phone else None)
    )

    tenant = Tenant(
        owner_user_id=user.id,
        client_prefix=f"wl{suffix[:4]}",
        name=f"WL Test Tenant {suffix}",
        evolution_instance_name=instance_name,
        evolution_instance_token=instance_token,
        whatsapp_phone=whatsapp_phone,
        plan=plan,
        is_active=is_active,
    )
    db_session.add(tenant)
    await db_session.flush()

    db_session.add(TenantSettings(tenant_id=tenant.id, locale="en"))
    await db_session.commit()
    await db_session.refresh(tenant)
    return tenant, user


async def _seed_master_user(db_session) -> Any:
    from app.core.security import get_password_hash
    from app.models import MasterProfile, User

    suffix = uuid.uuid4().hex[:8]
    user = User(
        username=f"wl_master_{suffix}",
        password_hash=get_password_hash("pass"),
        role="master",
    )
    db_session.add(user)
    await db_session.flush()
    db_session.add(
        MasterProfile(id=user.id, name=f"Master {suffix}", phone="+12025550001")
    )
    await db_session.commit()
    return user


async def _login_as(
    client: AsyncClient, username: str, password: str = "pass"
) -> dict[str, str]:
    response = await client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": password},
    )
    assert response.status_code == 200, f"Login failed: {response.text}"
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _patch_evolution(
    method_name: str, return_value: Any = None, side_effect: Any = None
):
    """Patch an EvolutionClient lifecycle method on the singleton."""
    target = f"app.services.evolution_client.evolution_client.{method_name}"
    return patch(
        target, new=AsyncMock(return_value=return_value, side_effect=side_effect)
    )


def _patch_decrypt(return_value: str = "decrypted-token-123"):
    """Patch decrypt_value in the service module to return a predictable token.

    The service uses ``from app.core.encryption import decrypt_value``, so
    we must patch at the usage site, not the origin module.
    """
    return patch(
        "app.services.whatsapp_link_service.decrypt_value", return_value=return_value
    )


# ── Auth / Role / Access Tests ──────────────────────────────────────────────


class TestAuthAndAuthorization:
    """Authentication and authorization for WhatsApp Link endpoints."""

    pytestmark = pytest.mark.asyncio

    STATUS_URL = "/api/v1/tenant/whatsapp-link/status"

    async def test_missing_jwt_returns_401(self, client: AsyncClient):
        """No JWT token → 401."""
        response = await client.get(self.STATUS_URL)
        assert response.status_code == 401

    async def test_client_role_returns_403(self, client: AsyncClient, db_session):
        """Client role is explicitly forbidden."""
        from app.core.security import get_password_hash
        from app.models import Client, Tenant, User

        suffix = uuid.uuid4().hex[:8]
        tuser = User(
            username=f"wl_t_{suffix}",
            password_hash=get_password_hash("pass"),
            role="tenant",
        )
        db_session.add(tuser)
        await db_session.flush()
        tenant = Tenant(
            owner_user_id=tuser.id,
            client_prefix=f"wc{suffix[:3]}",
            name="ClientTenant",
            is_active=True,
        )
        db_session.add(tenant)
        await db_session.flush()

        cuser = User(
            username=f"wl_c_{suffix}",
            password_hash=get_password_hash("pass"),
            role="client",
        )
        db_session.add(cuser)
        await db_session.flush()
        db_session.add(
            Client(
                tenant_id=tenant.id,
                owner_user_id=cuser.id,
                full_name="Test Client",
                username=f"wl_c_{suffix}",
                phone="+12025550002",
                is_active=True,
            )
        )
        await db_session.commit()

        headers = await _login_as(client, f"wl_c_{suffix}")
        response = await client.get(self.STATUS_URL, headers=headers)
        assert response.status_code == 403

    async def test_starter_tenant_admin_can_access_status(
        self, client: AsyncClient, db_session
    ):
        """Starter tenant admins can access WhatsApp self-linking status."""
        tenant, user = await _seed_tenant_with_evolution(
            db_session, plan=TENANT_PLAN_STARTER
        )
        headers = await _login_as(client, user.username)

        with _patch_decrypt():
            with _patch_evolution(
                "get_instance_status",
                return_value={"connected": False, "loggedIn": False},
            ):
                response = await client.get(self.STATUS_URL, headers=headers)
        assert response.status_code == 200
        assert response.json()["instance_name"] == tenant.evolution_instance_name

    async def test_master_support_can_access_starter_tenant(
        self, client: AsyncClient, db_session
    ):
        """Master support context bypasses Pro gate for starter tenant."""
        from app.core.security import create_access_token

        tenant, _ = await _seed_tenant_with_evolution(
            db_session, plan=TENANT_PLAN_STARTER
        )
        master = await _seed_master_user(db_session)

        # Master logs in and gets a token with active_tenant_id
        token = create_access_token(
            subject=str(master.id),
            role="master",
            active_tenant_id=str(tenant.id),
        )
        headers = {"Authorization": f"Bearer {token}"}

        with _patch_decrypt():
            with _patch_evolution(
                "get_instance_status",
                return_value={"connected": False, "loggedIn": False},
            ):
                response = await client.get(self.STATUS_URL, headers=headers)
        assert response.status_code == 200

    async def test_inactive_tenant_user_blocked(self, client: AsyncClient, db_session):
        """Inactive tenant gets 401 from get_active_tenant_id dependency."""
        from app.core.security import create_access_token

        tenant, user = await _seed_tenant_with_evolution(db_session, is_active=False)
        token = create_access_token(
            subject=str(user.id),
            role="tenant",
        )
        headers = {"Authorization": f"Bearer {token}"}
        response = await client.get(self.STATUS_URL, headers=headers)
        assert response.status_code == 401


# ── Status Endpoint ─────────────────────────────────────────────────────────


class TestGetStatus:
    """GET /api/v1/tenant/whatsapp-link/status"""

    pytestmark = pytest.mark.asyncio

    URL = "/api/v1/tenant/whatsapp-link/status"

    async def test_connected_both_flags_true(self, client: AsyncClient, db_session):
        """connected=true only when Evolution reports both connected and loggedIn."""
        tenant, user = await _seed_tenant_with_evolution(db_session)
        headers = await _login_as(client, user.username)

        with _patch_decrypt():
            with _patch_evolution(
                "get_instance_status",
                return_value={"connected": True, "loggedIn": True},
            ):
                response = await client.get(self.URL, headers=headers)

        assert response.status_code == 200
        data = response.json()
        assert data["connected"] is True
        assert data["phone"] == tenant.whatsapp_phone
        assert data["instance_name"] == tenant.evolution_instance_name

    async def test_connected_false_when_disconnected(
        self, client: AsyncClient, db_session
    ):
        """connected=false when Evolution reports disconnected."""
        tenant, user = await _seed_tenant_with_evolution(db_session)
        headers = await _login_as(client, user.username)

        with _patch_decrypt():
            with _patch_evolution(
                "get_instance_status",
                return_value={"connected": False, "loggedIn": False},
            ):
                response = await client.get(self.URL, headers=headers)

        assert response.status_code == 200
        assert response.json()["connected"] is False

    async def test_connected_false_when_loggedin_false(
        self, client: AsyncClient, db_session
    ):
        """connected=false when loggedIn is false even if connected is true."""
        tenant, user = await _seed_tenant_with_evolution(db_session)
        headers = await _login_as(client, user.username)

        with _patch_decrypt():
            with _patch_evolution(
                "get_instance_status",
                return_value={"connected": True, "loggedIn": False},
            ):
                response = await client.get(self.URL, headers=headers)

        assert response.status_code == 200
        assert response.json()["connected"] is False

    async def test_connected_false_when_connected_false(
        self, client: AsyncClient, db_session
    ):
        """connected=false when connected is false even if loggedIn is true."""
        tenant, user = await _seed_tenant_with_evolution(db_session)
        headers = await _login_as(client, user.username)

        with _patch_decrypt():
            with _patch_evolution(
                "get_instance_status",
                return_value={"connected": False, "loggedIn": True},
            ):
                response = await client.get(self.URL, headers=headers)

        assert response.status_code == 200
        assert response.json()["connected"] is False

    async def test_phone_is_null_when_not_set(self, client: AsyncClient, db_session):
        """phone is null when tenant has no whatsapp_phone."""
        tenant, user = await _seed_tenant_with_evolution(
            db_session, has_phone=False, phone=None
        )
        headers = await _login_as(client, user.username)

        with _patch_decrypt():
            with _patch_evolution(
                "get_instance_status",
                return_value={"connected": False, "loggedIn": False},
            ):
                response = await client.get(self.URL, headers=headers)

        assert response.status_code == 200
        assert response.json()["phone"] is None

    async def test_missing_instance_name_returns_400(
        self, client: AsyncClient, db_session
    ):
        """Missing evolution_instance_name → 400."""
        tenant, user = await _seed_tenant_with_evolution(
            db_session, has_instance_name=False
        )
        headers = await _login_as(client, user.username)
        response = await client.get(self.URL, headers=headers)
        assert response.status_code == 400
        assert (
            "instance_not_configured" in response.text
            or "not configured" in response.text.lower()
        )

    async def test_missing_instance_token_returns_400(
        self, client: AsyncClient, db_session
    ):
        """Missing evolution_instance_token → 400."""
        tenant, user = await _seed_tenant_with_evolution(
            db_session, has_instance_token=False
        )
        headers = await _login_as(client, user.username)
        response = await client.get(self.URL, headers=headers)
        assert response.status_code == 400


# ── Pair Endpoint ───────────────────────────────────────────────────────────


class TestPair:
    """POST /api/v1/tenant/whatsapp-link/pair"""

    pytestmark = pytest.mark.asyncio

    URL = "/api/v1/tenant/whatsapp-link/pair"

    async def test_success_returns_code(self, client: AsyncClient, db_session):
        """Empty body returns { code }."""
        tenant, user = await _seed_tenant_with_evolution(db_session)
        headers = await _login_as(client, user.username)

        with _patch_decrypt():
            with _patch_evolution(
                "get_instance_status",
                return_value={"connected": False, "loggedIn": False},
            ):
                with _patch_evolution(
                    "pair_instance", return_value={"code": "12345678"}
                ):
                    response = await client.post(self.URL, json={}, headers=headers)

        assert response.status_code == 200
        data = response.json()
        assert "code" in data
        assert data["code"] == "12345678"

    async def test_starter_tenant_admin_can_access_pair(
        self, client: AsyncClient, db_session
    ):
        """Starter tenant admins can request a WhatsApp pairing code."""
        tenant, user = await _seed_tenant_with_evolution(
            db_session, plan=TENANT_PLAN_STARTER
        )
        headers = await _login_as(client, user.username)

        with _patch_decrypt():
            with _patch_evolution(
                "get_instance_status",
                return_value={"connected": False, "loggedIn": False},
            ):
                with _patch_evolution(
                    "pair_instance", return_value={"code": "12345678"}
                ):
                    response = await client.post(self.URL, json={}, headers=headers)

        assert response.status_code == 200
        assert response.json()["code"] == "12345678"

    async def test_rejects_client_supplied_phone(self, client: AsyncClient, db_session):
        """Client-supplied phone is rejected via extra='forbid' → 422."""
        tenant, user = await _seed_tenant_with_evolution(db_session)
        headers = await _login_as(client, user.username)
        response = await client.post(
            self.URL, json={"phone": "+12025559999"}, headers=headers
        )
        assert response.status_code == 422

    async def test_no_phone_returns_400(self, client: AsyncClient, db_session):
        """Missing whatsapp_phone → 400."""
        tenant, user = await _seed_tenant_with_evolution(
            db_session, has_phone=False, phone=None
        )
        headers = await _login_as(client, user.username)

        with _patch_decrypt():
            with _patch_evolution(
                "get_instance_status",
                return_value={"connected": False, "loggedIn": False},
            ):
                response = await client.post(self.URL, json={}, headers=headers)

        assert response.status_code == 400
        assert "phone" in response.text.lower()

    async def test_already_connected_returns_409(self, client: AsyncClient, db_session):
        """Already connected → 409."""
        tenant, user = await _seed_tenant_with_evolution(db_session)
        headers = await _login_as(client, user.username)

        with _patch_decrypt():
            with _patch_evolution(
                "get_instance_status",
                return_value={"connected": True, "loggedIn": True},
            ):
                response = await client.post(self.URL, json={}, headers=headers)

        assert response.status_code == 409
        assert "already" in response.text.lower()

    async def test_no_phone_with_schema_still_rejects(
        self, client: AsyncClient, db_session
    ):
        """Empty body with no phone returns 400 (service validation), not 422."""
        tenant, user = await _seed_tenant_with_evolution(
            db_session, has_phone=False, phone=None
        )
        headers = await _login_as(client, user.username)

        with _patch_decrypt():
            with _patch_evolution(
                "get_instance_status",
                return_value={"connected": False, "loggedIn": False},
            ):
                response = await client.post(self.URL, json={}, headers=headers)

        assert response.status_code == 400


# ── QR Endpoint ─────────────────────────────────────────────────────────────


class TestGetQr:
    """GET /api/v1/tenant/whatsapp-link/qr"""

    pytestmark = pytest.mark.asyncio

    URL = "/api/v1/tenant/whatsapp-link/qr"

    async def test_success_returns_qrcode(self, client: AsyncClient, db_session):
        """Success returns { qrcode }."""
        tenant, user = await _seed_tenant_with_evolution(db_session)
        headers = await _login_as(client, user.username)

        with _patch_decrypt():
            with _patch_evolution(
                "get_instance_status",
                return_value={"connected": False, "loggedIn": False},
            ):
                with _patch_evolution(
                    "get_qr_code", return_value={"qrcode": "base64imagdata=="}
                ):
                    response = await client.get(self.URL, headers=headers)

        assert response.status_code == 200
        data = response.json()
        assert "qrcode" in data
        assert data["qrcode"] == "base64imagdata=="

    async def test_starter_tenant_admin_can_access_qr(
        self, client: AsyncClient, db_session
    ):
        """Starter tenant admins can retrieve a WhatsApp QR code."""
        tenant, user = await _seed_tenant_with_evolution(
            db_session, plan=TENANT_PLAN_STARTER
        )
        headers = await _login_as(client, user.username)

        with _patch_decrypt():
            with _patch_evolution(
                "get_instance_status",
                return_value={"connected": False, "loggedIn": False},
            ):
                with _patch_evolution(
                    "get_qr_code", return_value={"qrcode": "base64imagdata=="}
                ):
                    response = await client.get(self.URL, headers=headers)

        assert response.status_code == 200
        assert response.json()["qrcode"] == "base64imagdata=="

    async def test_no_phone_returns_400(self, client: AsyncClient, db_session):
        """Missing whatsapp_phone → 400."""
        tenant, user = await _seed_tenant_with_evolution(
            db_session, has_phone=False, phone=None
        )
        headers = await _login_as(client, user.username)

        with _patch_decrypt():
            with _patch_evolution(
                "get_instance_status",
                return_value={"connected": False, "loggedIn": False},
            ):
                response = await client.get(self.URL, headers=headers)

        assert response.status_code == 400

    async def test_already_connected_returns_409(self, client: AsyncClient, db_session):
        """Already connected → 409."""
        tenant, user = await _seed_tenant_with_evolution(db_session)
        headers = await _login_as(client, user.username)

        with _patch_decrypt():
            with _patch_evolution(
                "get_instance_status",
                return_value={"connected": True, "loggedIn": True},
            ):
                response = await client.get(self.URL, headers=headers)

        assert response.status_code == 409


# ── Disconnect Endpoint ─────────────────────────────────────────────────────


class TestDisconnect:
    """POST /api/v1/tenant/whatsapp-link/disconnect"""

    pytestmark = pytest.mark.asyncio

    URL = "/api/v1/tenant/whatsapp-link/disconnect"

    async def test_success_returns_connected_false(
        self, client: AsyncClient, db_session
    ):
        """Disconnect calls logout and returns { connected: false }."""
        tenant, user = await _seed_tenant_with_evolution(db_session)
        headers = await _login_as(client, user.username)

        with _patch_decrypt():
            with _patch_evolution("logout_instance", return_value=None):
                response = await client.post(self.URL, headers=headers)

        assert response.status_code == 200
        data = response.json()
        assert data["connected"] is False

    async def test_starter_tenant_admin_can_access_disconnect(
        self, client: AsyncClient, db_session
    ):
        """Starter tenant admins can disconnect their WhatsApp instance."""
        tenant, user = await _seed_tenant_with_evolution(
            db_session, plan=TENANT_PLAN_STARTER
        )
        headers = await _login_as(client, user.username)

        with _patch_decrypt():
            with _patch_evolution("logout_instance", return_value=None):
                response = await client.post(self.URL, headers=headers)

        assert response.status_code == 200
        assert response.json()["connected"] is False

    async def test_already_disconnected_returns_200(
        self, client: AsyncClient, db_session
    ):
        """Already disconnected is idempotent → 200."""
        tenant, user = await _seed_tenant_with_evolution(db_session)
        headers = await _login_as(client, user.username)

        with _patch_decrypt():
            with _patch_evolution("logout_instance", return_value=None):
                response = await client.post(self.URL, headers=headers)

        assert response.status_code == 200
        assert response.json()["connected"] is False


# ── Error Mapping ───────────────────────────────────────────────────────────


class TestErrorMapping:
    """Error mapping from EvolutionClientError to HTTP responses."""

    pytestmark = pytest.mark.asyncio

    URL = "/api/v1/tenant/whatsapp-link/status"

    async def test_evolution_downtime_returns_503(
        self, client: AsyncClient, db_session
    ):
        """Evolution network error → 503."""
        tenant, user = await _seed_tenant_with_evolution(db_session)
        headers = await _login_as(client, user.username)

        with _patch_decrypt():
            with _patch_evolution(
                "get_instance_status",
                side_effect=EvolutionClientError("service_unavailable"),
            ):
                response = await client.get(self.URL, headers=headers)

        assert response.status_code == 503

    async def test_invalid_instance_token_returns_502(
        self, client: AsyncClient, db_session
    ):
        """Invalid instance token → 502."""
        tenant, user = await _seed_tenant_with_evolution(db_session)
        headers = await _login_as(client, user.username)

        with _patch_decrypt():
            with _patch_evolution(
                "get_instance_status",
                side_effect=EvolutionClientError("invalid_instance_token"),
            ):
                response = await client.get(self.URL, headers=headers)

        assert response.status_code == 502

    async def test_decrypt_failure_returns_502(self, client: AsyncClient, db_session):
        """Token decryption failure → 502."""
        tenant, user = await _seed_tenant_with_evolution(db_session)
        headers = await _login_as(client, user.username)

        with _patch_decrypt(return_value=None):
            response = await client.get(self.URL, headers=headers)

        assert response.status_code == 502


# ── i18n Catalog Assertions ─────────────────────────────────────────────────


class TestI18nCatalogs:
    """Assert i18n catalog keys exist for WhatsApp link feature."""

    pytestmark = pytest.mark.asyncio

    ERROR_KEYS = [
        "errors.whatsapp_link.instance_not_configured",
        "errors.whatsapp_link.phone_required",
        "errors.whatsapp_link.already_connected",
        "errors.whatsapp_link.service_unavailable",
        "errors.whatsapp_link.invalid_instance_token",
        "errors.whatsapp_link.request_failed",
    ]

    FRONTEND_KEYS = [
        "frontend.whatsapp_link.section_title",
        "frontend.whatsapp_link.section_description",
        "frontend.whatsapp_link.heading",
        "frontend.whatsapp_link.description",
        "frontend.whatsapp_link.phone_label",
        "frontend.whatsapp_link.instance_label",
        "frontend.whatsapp_link.status_connected",
        "frontend.whatsapp_link.status_disconnected",
        "frontend.whatsapp_link.status_connecting",
        "frontend.whatsapp_link.no_phone_title",
        "frontend.whatsapp_link.no_phone_description",
        "frontend.whatsapp_link.pairing_tab",
        "frontend.whatsapp_link.qr_tab",
        "frontend.whatsapp_link.generate_code",
        "frontend.whatsapp_link.generating_code",
        "frontend.whatsapp_link.pairing_code_label",
        "frontend.whatsapp_link.pairing_code_instructions",
        "frontend.whatsapp_link.qr_instructions",
        "frontend.whatsapp_link.refresh_qr",
        "frontend.whatsapp_link.refreshing_qr",
        "frontend.whatsapp_link.qr_expires_in",
        "frontend.whatsapp_link.disconnect",
        "frontend.whatsapp_link.disconnecting",
        "frontend.whatsapp_link.disconnect_confirm_title",
        "frontend.whatsapp_link.disconnect_confirm_description",
        "frontend.whatsapp_link.success_linked",
        "frontend.whatsapp_link.success_disconnected",
        "frontend.whatsapp_link.error_load",
        "frontend.whatsapp_link.error_pair",
        "frontend.whatsapp_link.error_qr",
        "frontend.whatsapp_link.error_disconnect",
        "frontend.whatsapp_link.error_timeout",
        "frontend.whatsapp_link.error_unknown",
        "frontend.whatsapp_link.retry",
    ]

    def _check_catalog(
        self, catalog_name: str, catalog: dict[str, str], keys: list[str]
    ) -> None:
        missing = [k for k in keys if k not in catalog]
        assert not missing, f"{catalog_name} missing keys: {missing}"

    async def test_en_general_has_error_keys(self):
        from app.core.i18n.catalogs_en_general import _CATALOG_EN_GENERAL

        self._check_catalog("catalogs_en_general", _CATALOG_EN_GENERAL, self.ERROR_KEYS)

    async def test_es_general_has_error_keys(self):
        from app.core.i18n.catalogs_es_general import _CATALOG_ES_GENERAL

        self._check_catalog("catalogs_es_general", _CATALOG_ES_GENERAL, self.ERROR_KEYS)

    async def test_en_frontend_has_ui_keys(self):
        from app.core.i18n.catalogs_en_frontend import _CATALOG_EN_FRONTEND

        self._check_catalog(
            "catalogs_en_frontend", _CATALOG_EN_FRONTEND, self.FRONTEND_KEYS
        )

    async def test_es_frontend_has_ui_keys(self):
        from app.core.i18n.catalogs_es_frontend import _CATALOG_ES_FRONTEND

        self._check_catalog(
            "catalogs_es_frontend", _CATALOG_ES_FRONTEND, self.FRONTEND_KEYS
        )


# ── Missing Config Tests ────────────────────────────────────────────────────


class TestMissingConfigEndpoints:
    """All endpoints when instance config is missing."""

    pytestmark = pytest.mark.asyncio

    async def test_status_missing_instance_name_400(
        self, client: AsyncClient, db_session
    ):
        tenant, user = await _seed_tenant_with_evolution(
            db_session, has_instance_name=False
        )
        headers = await _login_as(client, user.username)
        response = await client.get(
            "/api/v1/tenant/whatsapp-link/status", headers=headers
        )
        assert response.status_code == 400

    async def test_pair_missing_instance_token_400(
        self, client: AsyncClient, db_session
    ):
        tenant, user = await _seed_tenant_with_evolution(
            db_session, has_instance_token=False
        )
        headers = await _login_as(client, user.username)
        response = await client.post(
            "/api/v1/tenant/whatsapp-link/pair", json={}, headers=headers
        )
        assert response.status_code == 400

    async def test_qr_missing_config_400(self, client: AsyncClient, db_session):
        tenant, user = await _seed_tenant_with_evolution(
            db_session, has_instance_name=False
        )
        headers = await _login_as(client, user.username)
        response = await client.get("/api/v1/tenant/whatsapp-link/qr", headers=headers)
        assert response.status_code == 400

    async def test_disconnect_missing_config_400(self, client: AsyncClient, db_session):
        tenant, user = await _seed_tenant_with_evolution(
            db_session, has_instance_name=False
        )
        headers = await _login_as(client, user.username)
        response = await client.post(
            "/api/v1/tenant/whatsapp-link/disconnect", headers=headers
        )
        assert response.status_code == 400
