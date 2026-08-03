"""Tests for Task 6: plan_price in service-catalog.csv and currency in account-profile.csv."""

from __future__ import annotations

import json
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.models import Tenant
from app.models.plan import Plan
from app.models.service import Service
from app.models.tenant_settings import TenantSettings
from app.services.export_worker import (
    _build_account_profile_csv,
    _build_json,
    _build_service_catalog_csv,
)

pytestmark = pytest.mark.asyncio


async def _tenant_for_user(db_session, user_id):
    result = await db_session.execute(
        select(Tenant).where(Tenant.owner_user_id == user_id)
    )
    return result.scalar_one_or_none()


# ── service-catalog.csv plan_price ─────────────────────────────


async def test_service_catalog_csv_includes_plan_price(db_session, active_tenant_user):
    """service-catalog.csv includes plan_price column after plan_name."""
    tenant = await _tenant_for_user(db_session, active_tenant_user.id)
    assert tenant is not None

    service = Service(tenant_id=tenant.id, name="Netflix", icon="simple-icons:netflix")
    db_session.add(service)
    await db_session.flush()

    priced_plan = Plan(
        tenant_id=tenant.id,
        service_id=service.id,
        name="Preciado",
        price=Decimal("12.50"),
    )
    unpriced_plan = Plan(
        tenant_id=tenant.id,
        service_id=service.id,
        name="Sin precio",
        price=None,
    )
    db_session.add_all([priced_plan, unpriced_plan])
    await db_session.commit()
    await db_session.refresh(priced_plan)
    await db_session.refresh(unpriced_plan)

    plans_by_service = {service.id: [priced_plan, unpriced_plan]}
    csv_content = _build_service_catalog_csv([service], plans_by_service, "UTC")
    lines = csv_content.strip().split("\n")

    # Header must include plan_price
    headers = [h.strip() for h in lines[0].split(",")]
    assert headers == [
        "service_name",
        "service_icon",
        "service_created_on",
        "service_updated_on",
        "plan_name",
        "plan_price",
        "plan_created_on",
        "plan_updated_on",
    ]

    # Priced plan row
    priced_row = [v.strip() for v in lines[1].split(",")]
    assert priced_row[4] == "Preciado"  # plan_name
    assert priced_row[5] == "12.50"  # plan_price formatted

    # Unpriced plan row
    unpriced_row = [v.strip() for v in lines[2].split(",")]
    assert unpriced_row[4] == "Sin precio"
    assert unpriced_row[5] == ""  # empty when price is None


async def test_service_catalog_json_plan_includes_plan_price(
    db_session, active_tenant_user
):
    """JSON service_catalog plans include plan_price."""
    tenant = await _tenant_for_user(db_session, active_tenant_user.id)
    assert tenant is not None

    service = Service(tenant_id=tenant.id, name="Netflix")
    db_session.add(service)
    await db_session.flush()

    plan = Plan(
        tenant_id=tenant.id,
        service_id=service.id,
        name="Standard",
        price=Decimal("9.99"),
    )
    db_session.add(plan)
    await db_session.commit()
    await db_session.refresh(plan)

    plans_by_service = {service.id: [plan]}
    data = json.loads(
        _build_json(
            tenant,
            "en",
            "UTC",
            services=[service],
            plans_by_service=plans_by_service,
        )
    )
    plan_entry = data["service_catalog"][0]["plans"][0]
    assert plan_entry["plan_price"] == "9.99"


# ── account-profile.csv currency ───────────────────────────────


async def test_account_profile_csv_includes_currency(db_session, active_tenant_user):
    """account-profile.csv includes currency column from tenant settings."""
    tenant = await _tenant_for_user(db_session, active_tenant_user.id)
    assert tenant is not None

    csv_content = _build_account_profile_csv(tenant, "en", "UTC", currency="VES")
    lines = csv_content.strip().split("\n")

    headers = [h.strip() for h in lines[0].split(",")]
    assert "currency" in headers
    assert headers == [
        "account_name",
        "whatsapp_phone",
        "login_username",
        "current_plan",
        "preferred_language",
        "time_zone",
        "currency",
    ]

    # Data row should have VES
    row = [v.strip() for v in lines[1].split(",")]
    currency_idx = headers.index("currency")
    assert row[currency_idx] == "VES"


async def test_account_profile_csv_empty_currency_when_unset(
    db_session, active_tenant_user
):
    """account-profile.csv shows empty currency when tenant settings have no currency."""
    tenant = await _tenant_for_user(db_session, active_tenant_user.id)
    assert tenant is not None

    # Ensure currency is None
    settings = await db_session.execute(
        select(TenantSettings).where(TenantSettings.tenant_id == tenant.id)
    )
    tenant_settings = settings.scalar_one()
    tenant_settings.currency = None
    await db_session.commit()

    csv_content = _build_account_profile_csv(tenant, "en", "UTC")
    lines = csv_content.strip().split("\n")
    headers = [h.strip() for h in lines[0].split(",")]
    row = [v.strip() for v in lines[1].split(",")]
    currency_idx = headers.index("currency")
    assert row[currency_idx] == ""


async def test_account_profile_json_includes_currency(db_session, active_tenant_user):
    """JSON account_profile includes currency."""
    tenant = await _tenant_for_user(db_session, active_tenant_user.id)
    assert tenant is not None

    data = json.loads(_build_json(tenant, "en", "UTC", currency="VES"))
    assert data["account_profile"]["currency"] == "VES"


async def test_account_profile_json_null_currency_when_unset(
    db_session, active_tenant_user
):
    """JSON account_profile has null currency when unset."""
    tenant = await _tenant_for_user(db_session, active_tenant_user.id)
    assert tenant is not None

    settings = await db_session.execute(
        select(TenantSettings).where(TenantSettings.tenant_id == tenant.id)
    )
    tenant_settings = settings.scalar_one()
    tenant_settings.currency = None
    await db_session.commit()

    data = json.loads(_build_json(tenant, "en", "UTC"))
    assert data["account_profile"]["currency"] is None
