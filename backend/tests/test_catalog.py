import pytest
from datetime import datetime, timezone
from sqlalchemy.exc import IntegrityError
from unittest.mock import AsyncMock
from uuid import uuid4

from app.core.errors import UserFacingError
from app.core.security import get_password_hash
from app.models import Client, Plan, Service, Subscription, Tenant, User
from app.services.catalog_service import CatalogService


pytestmark = pytest.mark.asyncio


async def _tenant_id(db_session, user):
    result = await db_session.execute(
        Tenant.__table__.select().where(Tenant.owner_user_id == user.id)
    )
    return result.first()._mapping["id"]


async def _login(client, username="tenant", password="tenant-password"):
    response = await client.post(
        "/api/v1/auth/login", json={"username": username, "password": password}
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


async def _catalog_fixture(db_session, tenant_id):
    client_user = User(
        username=f"client_{uuid4().hex[:8]}",
        password_hash=get_password_hash("client-password"),
        role="client",
    )
    db_session.add(client_user)
    await db_session.flush()
    client = Client(
        tenant_id=tenant_id,
        owner_user_id=client_user.id,
        full_name="Cliente Demo",
        username=f"client_{uuid4().hex[:8]}",
        phone="584241234567",
        is_active=True,
    )
    db_session.add(client)
    await db_session.flush()

    service = Service(tenant_id=tenant_id, name="Netflix")
    db_session.add(service)
    await db_session.flush()
    basic = Plan(tenant_id=tenant_id, service_id=service.id, name="Basic")
    premium = Plan(tenant_id=tenant_id, service_id=service.id, name="Premium")
    db_session.add_all([basic, premium])
    await db_session.flush()

    active = Subscription(
        tenant_id=tenant_id,
        client_id=client.id,
        service_id=service.id,
        plan_id=premium.id,
        streaming_email="active@example.com",
        duration_type="1_month",
        starts_at=datetime(2026, 6, 1, tzinfo=timezone.utc),
        expires_at=datetime(2026, 7, 1, tzinfo=timezone.utc),
        status="active",
    )
    historical = Subscription(
        tenant_id=tenant_id,
        client_id=client.id,
        service_id=service.id,
        plan_id=basic.id,
        streaming_email="old@example.com",
        duration_type="1_month",
        starts_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        expires_at=datetime(2026, 2, 1, tzinfo=timezone.utc),
        status="expired",
    )
    db_session.add_all([active, historical])
    await db_session.commit()
    return service, basic, premium, active, historical


async def test_tenant_service_and_plan_crud(client, active_tenant_user):
    headers = await _login(client)
    service = await client.post(
        "/api/v1/catalog/services", json={"name": "Consultoría"}, headers=headers
    )
    assert service.status_code == 201
    sid = service.json()["id"]
    duplicate = await client.post(
        "/api/v1/catalog/services", json={"name": "consultoría"}, headers=headers
    )
    assert duplicate.status_code == 409
    plan = await client.post(
        f"/api/v1/catalog/services/{sid}/plans",
        json={"name": "Básico"},
        headers=headers,
    )
    assert plan.status_code == 201
    pid = plan.json()["id"]
    duplicate_plan = await client.post(
        f"/api/v1/catalog/services/{sid}/plans",
        json={"name": "básico"},
        headers=headers,
    )
    assert duplicate_plan.status_code == 409
    updated = await client.put(
        f"/api/v1/catalog/services/{sid}/plans/{pid}",
        json={"name": "Pro"},
        headers=headers,
    )
    assert updated.status_code == 200
    plain_delete = await client.delete(
        f"/api/v1/catalog/services/{sid}", headers=headers
    )
    assert plain_delete.status_code == 400
    # Re-create for confirmed-delete test
    service2 = await client.post(
        "/api/v1/catalog/services", json={"name": "Streaming"}, headers=headers
    )
    assert service2.status_code == 201
    sid2 = service2.json()["id"]
    confirmed_delete = await client.delete(
        f"/api/v1/catalog/services/{sid2}?confirm=true", headers=headers
    )
    assert confirmed_delete.status_code == 204
    plans = await client.get(f"/api/v1/catalog/services/{sid2}/plans", headers=headers)
    assert plans.status_code == 404


async def test_master_without_context_forbidden(client, master_user):
    headers = await _login(client, "master", "master-password")
    response = await client.get("/api/v1/catalog/services", headers=headers)
    assert response.status_code == 403


async def test_master_switched_context_can_manage_catalog(
    client, active_tenant_user, auth_headers, db_session
):
    tenant_id = str(await _tenant_id(db_session, active_tenant_user))
    switched = await client.post(
        "/api/v1/auth/switch-tenant",
        json={"tenant_id": tenant_id},
        headers=auth_headers,
    )
    assert switched.status_code == 200
    headers = {"Authorization": f"Bearer {switched.json()['access_token']}"}
    response = await client.post(
        "/api/v1/catalog/services", json={"name": "Soporte"}, headers=headers
    )
    assert response.status_code == 201


async def test_catalog_commit_integrity_error_maps_to_value_error():
    db = AsyncMock()
    db.commit.side_effect = IntegrityError("insert", {}, Exception("unique violation"))

    with pytest.raises(UserFacingError, match="service_name_already_exists"):
        await CatalogService()._commit_catalog_change(db, "service_name_already_exists")

    db.rollback.assert_awaited_once()


async def test_catalog_delete_preview_and_confirmed_service_cascade(
    client, active_tenant_user, db_session
):
    tenant_id = await _tenant_id(db_session, active_tenant_user)
    service, basic, premium, active, historical = await _catalog_fixture(
        db_session, tenant_id
    )
    headers = await _login(client)

    preview = await client.get(
        f"/api/v1/catalog/services/{service.id}/delete-preview?page=1&page_size=10",
        headers=headers,
    )
    assert preview.status_code == 200
    payload = preview.json()
    assert payload["target_type"] == "service"
    assert payload["target_name"] == "Netflix"
    assert payload["affected_plan_count"] == 2
    assert payload["active_subscription_count"] == 1
    assert payload["historical_subscription_count"] == 1
    assert payload["total_subscription_count"] == 2
    assert payload["active_subscriptions"][0]["streaming_email"] == "active@example.com"
    assert "historical" in payload["note"].lower() or "hist" in payload["note"].lower()

    denied = await client.delete(
        f"/api/v1/catalog/services/{service.id}", headers=headers
    )
    assert denied.status_code == 400

    deleted = await client.delete(
        f"/api/v1/catalog/services/{service.id}?confirm=true", headers=headers
    )
    assert deleted.status_code == 204

    assert (
        await client.get(f"/api/v1/catalog/services/{service.id}", headers=headers)
    ).status_code == 404
    assert (
        await client.get(
            f"/api/v1/catalog/services/{service.id}/plans", headers=headers
        )
    ).status_code == 404


async def test_catalog_delete_preview_and_confirmed_plan_cascade(
    client, active_tenant_user, db_session
):
    tenant_id = await _tenant_id(db_session, active_tenant_user)
    service, basic, premium, active, historical = await _catalog_fixture(
        db_session, tenant_id
    )
    headers = await _login(client)

    preview = await client.get(
        f"/api/v1/catalog/services/{service.id}/plans/{premium.id}/delete-preview?page=1&page_size=10",
        headers=headers,
    )
    assert preview.status_code == 200
    payload = preview.json()
    assert payload["target_type"] == "plan"
    assert payload["target_name"] == "Premium"
    assert payload["affected_plan_count"] == 0
    assert payload["active_subscription_count"] == 1
    assert payload["historical_subscription_count"] == 0
    assert payload["total_subscription_count"] == 1

    denied = await client.delete(
        f"/api/v1/catalog/services/{service.id}/plans/{premium.id}", headers=headers
    )
    assert denied.status_code == 400

    deleted = await client.delete(
        f"/api/v1/catalog/services/{service.id}/plans/{premium.id}?confirm=true",
        headers=headers,
    )
    assert deleted.status_code == 204

    plans = await client.get(
        f"/api/v1/catalog/services/{service.id}/plans", headers=headers
    )
    assert plans.status_code == 200
    assert [plan["name"] for plan in plans.json()] == ["Basic"]


async def test_cross_tenant_isolation(client, active_tenant_user, db_session):
    """Tenant A cannot access, delete, or list Tenant B catalog objects."""
    # Create Tenant A catalog data
    tenant_a_id = await _tenant_id(db_session, active_tenant_user)
    svc_a, *_ = await _catalog_fixture(db_session, tenant_a_id)
    headers_a = await _login(client)

    # Tenant A can see their own data
    resp = await client.get(f"/api/v1/catalog/services/{svc_a.id}", headers=headers_a)
    assert resp.status_code == 200
    assert resp.json()["name"] == "Netflix"

    resp = await client.get(
        f"/api/v1/catalog/services/{svc_a.id}/plans", headers=headers_a
    )
    assert resp.status_code == 200

    # Create Tenant B user and tenant
    tenant_b_user = User(
        username=f"other_tenant_{uuid4().hex[:8]}",
        password_hash=get_password_hash("other-password"),
        role="tenant",
    )
    db_session.add(tenant_b_user)
    await db_session.flush()
    tenant_b = Tenant(
        owner_user_id=tenant_b_user.id,
        client_prefix="oth01",
        name="Other Tenant",
        whatsapp_phone="+12015559999",
        is_active=True,
    )
    db_session.add(tenant_b)
    await db_session.commit()

    # Create Tenant B catalog data
    tenant_b_id = await _tenant_id(db_session, tenant_b_user)
    svc_b, *_ = await _catalog_fixture(db_session, tenant_b_id)

    # Login as Tenant B
    headers_b = await _login(
        client, username=tenant_b_user.username, password="other-password"
    )

    # Tenant B can see their own data
    resp = await client.get(f"/api/v1/catalog/services/{svc_b.id}", headers=headers_b)
    assert resp.status_code == 200

    # Tenant B CANNOT access Tenant A's service → 404
    resp = await client.get(f"/api/v1/catalog/services/{svc_a.id}", headers=headers_b)
    assert resp.status_code == 404

    # Tenant B CANNOT list Tenant A's service plans → 404
    resp = await client.get(
        f"/api/v1/catalog/services/{svc_a.id}/plans", headers=headers_b
    )
    assert resp.status_code == 404

    # Tenant B CANNOT delete Tenant A's service
    resp = await client.delete(
        f"/api/v1/catalog/services/{svc_a.id}", headers=headers_b
    )
    assert resp.status_code == 400
    resp = await client.delete(
        f"/api/v1/catalog/services/{svc_a.id}?confirm=true", headers=headers_b
    )
    assert resp.status_code == 404

    # Confirm Tenant A's data still exists despite Tenant B's delete attempts
    resp = await client.get(f"/api/v1/catalog/services/{svc_a.id}", headers=headers_a)
    assert resp.status_code == 200

    # Tenant B's listing does not include Tenant A's service
    resp = await client.get("/api/v1/catalog/services", headers=headers_b)
    assert resp.status_code == 200
    service_ids = [s["id"] for s in resp.json()]
    assert str(svc_a.id) not in service_ids
    assert str(svc_b.id) in service_ids


async def test_plan_duplicate_name_is_scoped_to_same_service(
    client, active_tenant_user
):
    headers = await _login(client)
    one = await client.post(
        "/api/v1/catalog/services", json={"name": "Netflix"}, headers=headers
    )
    two = await client.post(
        "/api/v1/catalog/services", json={"name": "Disney"}, headers=headers
    )
    assert one.status_code == 201
    assert two.status_code == 201

    first_plan = await client.post(
        f"/api/v1/catalog/services/{one.json()['id']}/plans",
        json={"name": "Premium"},
        headers=headers,
    )
    same_other_service = await client.post(
        f"/api/v1/catalog/services/{two.json()['id']}/plans",
        json={"name": "Premium"},
        headers=headers,
    )
    duplicate_same_service = await client.post(
        f"/api/v1/catalog/services/{one.json()['id']}/plans",
        json={"name": "premium"},
        headers=headers,
    )

    assert first_plan.status_code == 201
    assert same_other_service.status_code == 201
    assert duplicate_same_service.status_code == 409


# ── Service Icon Tests ──────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "icon",
    ["netflix", "Simple-Icons:netflix", "simple-icons:", "a" * 256],
)
async def test_service_icon_rejects_invalid_references(
    client, active_tenant_user, icon: str
):
    headers = await _login(client)
    response = await client.post(
        "/api/v1/catalog/services",
        json={"name": "Icon validation", "icon": icon},
        headers=headers,
    )
    assert response.status_code == 422


async def test_service_icon_create_preserve_replace_and_clear(
    client, active_tenant_user
):
    headers = await _login(client)
    created = await client.post(
        "/api/v1/catalog/services",
        json={"name": "Netflix", "icon": "simple-icons:netflix"},
        headers=headers,
    )
    assert created.status_code == 201
    service_id = created.json()["id"]
    assert created.json()["icon"] == "simple-icons:netflix"

    renamed = await client.put(
        f"/api/v1/catalog/services/{service_id}",
        json={"name": "Netflix Premium"},
        headers=headers,
    )
    assert renamed.json()["icon"] == "simple-icons:netflix"

    replaced = await client.put(
        f"/api/v1/catalog/services/{service_id}",
        json={"icon": "logos:netflix-icon"},
        headers=headers,
    )
    assert replaced.json()["icon"] == "logos:netflix-icon"

    cleared = await client.put(
        f"/api/v1/catalog/services/{service_id}",
        json={"icon": None},
        headers=headers,
    )
    assert cleared.json()["icon"] is None


async def test_service_icon_save_does_not_call_iconify(
    db_session, active_tenant_user, monkeypatch
):
    tenant_id = await _tenant_id(db_session, active_tenant_user)
    request = AsyncMock(side_effect=AssertionError("unexpected external HTTP request"))
    monkeypatch.setattr("httpx.AsyncClient.request", request)

    from app.schemas.catalog import ServiceCreate

    saved = await CatalogService().create_service(
        db_session,
        tenant_id,
        ServiceCreate(name="Offline-safe", icon="mdi:cloud-off-outline"),
    )

    assert saved.icon == "mdi:cloud-off-outline"
    request.assert_not_awaited()


# --- Finding 1: cross-tenant icon isolation ---


async def test_cross_tenant_icon_isolation(client, active_tenant_user, db_session):
    """Tenant B cannot see or overwrite Tenant A's service icon."""
    headers_a = await _login(client)

    # Create a service with an icon for Tenant A
    created = await client.post(
        "/api/v1/catalog/services",
        json={"name": "Spotify", "icon": "simple-icons:spotify"},
        headers=headers_a,
    )
    assert created.status_code == 201
    svc_a_id = created.json()["id"]
    assert created.json()["icon"] == "simple-icons:spotify"

    # Create Tenant B user
    tenant_b_user = User(
        username=f"isolated_{uuid4().hex[:8]}",
        password_hash=get_password_hash("isolated-password"),
        role="tenant",
    )
    db_session.add(tenant_b_user)
    await db_session.flush()
    tenant_b = Tenant(
        owner_user_id=tenant_b_user.id,
        client_prefix="iso01",
        name="Isolated Tenant",
        whatsapp_phone="+12015558888",
        is_active=True,
    )
    db_session.add(tenant_b)
    await db_session.commit()

    headers_b = await _login(
        client, username=tenant_b_user.username, password="isolated-password"
    )

    # Tenant B GET → 404 (no icon leak)
    resp = await client.get(f"/api/v1/catalog/services/{svc_a_id}", headers=headers_b)
    assert resp.status_code == 404

    # Tenant B PUT → 404 (cannot overwrite icon)
    resp = await client.put(
        f"/api/v1/catalog/services/{svc_a_id}",
        json={"icon": "logos:spotify-icon"},
        headers=headers_b,
    )
    assert resp.status_code == 404

    # Tenant A's icon is untouched
    resp = await client.get(f"/api/v1/catalog/services/{svc_a_id}", headers=headers_a)
    assert resp.status_code == 200
    assert resp.json()["icon"] == "simple-icons:spotify"


# --- Finding 2: empty/omitted icon → null ---


async def test_service_icon_omitted_on_create_returns_null(client, active_tenant_user):
    headers = await _login(client)
    resp = await client.post(
        "/api/v1/catalog/services",
        json={"name": "No Icon Service"},
        headers=headers,
    )
    assert resp.status_code == 201
    assert resp.json()["icon"] is None


async def test_service_icon_empty_string_on_create_returns_null(
    client, active_tenant_user
):
    headers = await _login(client)
    resp = await client.post(
        "/api/v1/catalog/services",
        json={"name": "Empty Icon Service", "icon": ""},
        headers=headers,
    )
    assert resp.status_code == 201
    assert resp.json()["icon"] is None


# --- Finding 3: non-string icon input rejected ---


async def test_service_icon_rejects_non_string_input(client, active_tenant_user):
    headers = await _login(client)
    resp = await client.post(
        "/api/v1/catalog/services",
        json={"name": "Bad Icon Type", "icon": 42},
        headers=headers,
    )
    assert resp.status_code == 422


async def test_service_icon_rejects_boolean_input(client, active_tenant_user):
    headers = await _login(client)
    resp = await client.post(
        "/api/v1/catalog/services",
        json={"name": "Bool Icon", "icon": True},
        headers=headers,
    )
    assert resp.status_code == 422


async def test_plan_price_column_persists(db_session, active_tenant_user):
    tenant_id = await _tenant_id(db_session, active_tenant_user)
    service = Service(tenant_id=tenant_id, name="Price Test Service")
    db_session.add(service)
    await db_session.flush()

    plan = Plan(
        tenant_id=tenant_id,
        service_id=service.id,
        name="Basico",
        price=12.50,
    )
    db_session.add(plan)
    await db_session.commit()
    await db_session.refresh(plan)

    assert plan.price == 12.50


# ── Plan Price CRUD Tests ───────────────────────────────────────────────────


async def test_create_plan_with_price(db_session, active_tenant_user):
    tenant_id = await _tenant_id(db_session, active_tenant_user)
    service = Service(tenant_id=tenant_id, name="Price CRUD Service")
    db_session.add(service)
    await db_session.flush()
    await db_session.commit()

    from decimal import Decimal
    from app.schemas.catalog import PlanCreate

    plan = await CatalogService().create_plan(
        db_session,
        tenant_id,
        service.id,
        PlanCreate(name="Basico", price=Decimal("12.50")),
    )
    assert plan is not None
    assert plan.price == Decimal("12.50")


async def test_create_plan_without_price(db_session, active_tenant_user):
    tenant_id = await _tenant_id(db_session, active_tenant_user)
    service = Service(tenant_id=tenant_id, name="Price CRUD NoPrice")
    db_session.add(service)
    await db_session.flush()
    await db_session.commit()

    from app.schemas.catalog import PlanCreate

    plan = await CatalogService().create_plan(
        db_session,
        tenant_id,
        service.id,
        PlanCreate(name="Gratis"),
    )
    assert plan is not None
    assert plan.price is None


async def test_update_plan_price_and_clear(db_session, active_tenant_user):
    tenant_id = await _tenant_id(db_session, active_tenant_user)
    service = Service(tenant_id=tenant_id, name="Price Update Service")
    db_session.add(service)
    await db_session.flush()
    await db_session.commit()

    from decimal import Decimal
    from app.schemas.catalog import PlanCreate, PlanUpdate

    svc = CatalogService()
    plan = await svc.create_plan(
        db_session, tenant_id, service.id, PlanCreate(name="P1")
    )
    assert plan is not None

    # Set price
    updated = await svc.update_plan(
        db_session, tenant_id, service.id, plan.id, PlanUpdate(price=Decimal("9.99"))
    )
    assert updated is not None
    assert updated.price == Decimal("9.99")

    # Rename must NOT clobber price
    renamed = await svc.update_plan(
        db_session, tenant_id, service.id, plan.id, PlanUpdate(name="P1 renombrado")
    )
    assert renamed is not None
    assert renamed.price == Decimal("9.99")

    # Clear price
    cleared = await svc.update_plan(
        db_session, tenant_id, service.id, plan.id, PlanUpdate(price=None)
    )
    assert cleared is not None
    assert cleared.price is None


async def test_plan_price_endpoint_create_and_update(client, active_tenant_user):
    headers = await _login(client)
    # Create service
    svc_resp = await client.post(
        "/api/v1/catalog/services",
        json={"name": "Price Endpoint Service"},
        headers=headers,
    )
    assert svc_resp.status_code == 201
    sid = svc_resp.json()["id"]

    # Create plan with price
    plan_resp = await client.post(
        f"/api/v1/catalog/services/{sid}/plans",
        json={"name": "Premium", "price": "12.50"},
        headers=headers,
    )
    assert plan_resp.status_code == 201
    pid = plan_resp.json()["id"]
    assert plan_resp.json()["price"] == "12.50"

    # Update plan: set new price
    update_resp = await client.put(
        f"/api/v1/catalog/services/{sid}/plans/{pid}",
        json={"price": "19.99"},
        headers=headers,
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["price"] == "19.99"

    # Update plan: clear price
    clear_resp = await client.put(
        f"/api/v1/catalog/services/{sid}/plans/{pid}",
        json={"price": None},
        headers=headers,
    )
    assert clear_resp.status_code == 200
    assert clear_resp.json()["price"] is None

    # Update plan: negative price → 422
    neg_resp = await client.put(
        f"/api/v1/catalog/services/{sid}/plans/{pid}",
        json={"price": "-1"},
        headers=headers,
    )
    assert neg_resp.status_code == 422
