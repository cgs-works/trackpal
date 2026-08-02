"""Tests for Dashboard API — plan_price and currency fields."""

from __future__ import annotations

from typing import Any

import pytest
from httpx import AsyncClient


pytestmark = pytest.mark.asyncio


# ===================================================================
# Helpers
# ===================================================================


async def _login(client: AsyncClient, username: str, password: str) -> str:
    """Return a bearer token for the given user."""
    resp = await client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": password},
    )
    return resp.json()["access_token"]


# ===================================================================
# Client dashboard includes plan_price and currency
# ===================================================================


class TestClientDashboardPlanPriceCurrency:
    """GET /api/v1/dashboard for client includes plan_price and currency."""

    async def test_client_dashboard_includes_plan_price_and_currency(
        self,
        client: AsyncClient,
        active_tenant_user: Any,
        active_client_user: Any,
        db_session: Any,
    ) -> None:
        """Client dashboard returns plan_price and currency when configured."""
        from decimal import Decimal
        from sqlalchemy import select

        from app.models import (
            Plan,
            Service,
            Subscription,
            Tenant,
            TenantSettings,
        )

        # Load the tenant
        result = await db_session.execute(
            select(Tenant).where(Tenant.owner_user_id == active_tenant_user.id)
        )
        tenant = result.scalar_one()

        # Set currency on tenant settings
        settings_result = await db_session.execute(
            select(TenantSettings).where(TenantSettings.tenant_id == tenant.id)
        )
        ts = settings_result.scalar_one()
        ts.currency = "VES"

        # Create a service + plan with price
        service = Service(tenant_id=tenant.id, name="Netflix")
        db_session.add(service)
        await db_session.flush()

        plan = Plan(
            tenant_id=tenant.id,
            service_id=service.id,
            name="Premium",
            price=Decimal("12.50"),
        )
        db_session.add(plan)
        await db_session.flush()

        # Create a client user and client record
        from app.core.security import get_password_hash
        from app.models import Client, User

        client_user = User(
            username="dash_client_1",
            password_hash=get_password_hash("pass"),
            role="client",
        )
        db_session.add(client_user)
        await db_session.flush()

        client_record = Client(
            tenant_id=tenant.id,
            owner_user_id=client_user.id,
            full_name="Dashboard Client",
            username="dash_client_1",
            phone="+12015550999",
            is_active=True,
        )
        db_session.add(client_record)
        await db_session.flush()

        # Create an active subscription
        from datetime import datetime, timedelta, timezone

        now = datetime.now(timezone.utc)
        sub = Subscription(
            tenant_id=tenant.id,
            client_id=client_record.id,
            service_id=service.id,
            plan_id=plan.id,
            streaming_email="test@test.com",
            duration_type="1_month",
            starts_at=now,
            expires_at=now + timedelta(days=30),
            status="active",
        )
        db_session.add(sub)
        await db_session.commit()

        # Login as the client
        token = await _login(client, "dash_client_1", "pass")
        headers = {"Authorization": f"Bearer {token}"}

        # Call dashboard
        response = await client.get("/api/v1/dashboard", headers=headers)
        assert response.status_code == 200

        body = response.json()

        # Assert currency
        assert body["currency"] == {
            "code": "VES",
            "symbol": "Bs.",
            "minor_units": 2,
        }

        # Assert plan_price on subscription
        assert len(body["subscriptions"]) == 1
        assert body["subscriptions"][0]["plan_price"] == "12.50"

    async def test_client_dashboard_plan_price_none_when_not_set(
        self,
        client: AsyncClient,
        active_tenant_user: Any,
        active_client_user: Any,
        db_session: Any,
    ) -> None:
        """Client dashboard returns plan_price=null when plan has no price."""
        from sqlalchemy import select

        from app.models import Plan, Service, Subscription, Tenant

        result = await db_session.execute(
            select(Tenant).where(Tenant.owner_user_id == active_tenant_user.id)
        )
        tenant = result.scalar_one()

        service = Service(tenant_id=tenant.id, name="Hulu")
        db_session.add(service)
        await db_session.flush()

        plan = Plan(
            tenant_id=tenant.id,
            service_id=service.id,
            name="Basic",
            price=None,
        )
        db_session.add(plan)
        await db_session.flush()

        from app.core.security import get_password_hash
        from app.models import Client, User

        client_user = User(
            username="dash_client_2",
            password_hash=get_password_hash("pass"),
            role="client",
        )
        db_session.add(client_user)
        await db_session.flush()

        client_record = Client(
            tenant_id=tenant.id,
            owner_user_id=client_user.id,
            full_name="No Price Client",
            username="dash_client_2",
            phone="+12015550998",
            is_active=True,
        )
        db_session.add(client_record)
        await db_session.flush()

        from datetime import datetime, timedelta, timezone

        now = datetime.now(timezone.utc)
        sub = Subscription(
            tenant_id=tenant.id,
            client_id=client_record.id,
            service_id=service.id,
            plan_id=plan.id,
            streaming_email="test@test.com",
            duration_type="1_month",
            starts_at=now,
            expires_at=now + timedelta(days=30),
            status="active",
        )
        db_session.add(sub)
        await db_session.commit()

        token = await _login(client, "dash_client_2", "pass")
        headers = {"Authorization": f"Bearer {token}"}

        response = await client.get("/api/v1/dashboard", headers=headers)
        assert response.status_code == 200

        body = response.json()
        assert len(body["subscriptions"]) == 1
        assert body["subscriptions"][0]["plan_price"] is None

    async def test_client_dashboard_currency_none_when_not_configured(
        self,
        client: AsyncClient,
        active_tenant_user: Any,
        active_client_user: Any,
        db_session: Any,
    ) -> None:
        """Client dashboard returns currency=null when tenant has no currency."""
        from sqlalchemy import select

        from app.models import Tenant, TenantSettings

        result = await db_session.execute(
            select(Tenant).where(Tenant.owner_user_id == active_tenant_user.id)
        )
        tenant = result.scalar_one()

        settings_result = await db_session.execute(
            select(TenantSettings).where(TenantSettings.tenant_id == tenant.id)
        )
        ts = settings_result.scalar_one()
        ts.currency = None
        await db_session.commit()

        token = await _login(client, active_tenant_user.username, "tenant-password")
        headers = {"Authorization": f"Bearer {token}"}

        # We need a client user to test client dashboard
        # Use the active_client_user fixture
        from app.core.security import get_password_hash
        from app.models import Client, User

        client_user = User(
            username="dash_client_3",
            password_hash=get_password_hash("pass"),
            role="client",
        )
        db_session.add(client_user)
        await db_session.flush()

        client_record = Client(
            tenant_id=tenant.id,
            owner_user_id=client_user.id,
            full_name="No Currency Client",
            username="dash_client_3",
            phone="+12015550997",
            is_active=True,
        )
        db_session.add(client_record)
        await db_session.commit()

        token = await _login(client, "dash_client_3", "pass")
        headers = {"Authorization": f"Bearer {token}"}

        response = await client.get("/api/v1/dashboard", headers=headers)
        assert response.status_code == 200

        body = response.json()
        assert body["currency"] is None
