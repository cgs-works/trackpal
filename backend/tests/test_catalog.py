import pytest

from app.models import Tenant


pytestmark = pytest.mark.asyncio


async def _tenant_id(db_session, user):
    result = await db_session.execute(Tenant.__table__.select().where(Tenant.owner_user_id == user.id))
    return result.first()._mapping["id"]


async def _login(client, username="tenant", password="tenant-password"):
    response = await client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


async def test_tenant_service_and_plan_crud(client, active_tenant_user):
    headers = await _login(client)
    service = await client.post("/api/v1/catalog/services", json={"name": "Consultoría"}, headers=headers)
    assert service.status_code == 201
    sid = service.json()["id"]
    duplicate = await client.post("/api/v1/catalog/services", json={"name": "consultoría"}, headers=headers)
    assert duplicate.status_code == 409
    plan = await client.post(f"/api/v1/catalog/services/{sid}/plans", json={"name": "Básico"}, headers=headers)
    assert plan.status_code == 201
    pid = plan.json()["id"]
    duplicate_plan = await client.post(f"/api/v1/catalog/services/{sid}/plans", json={"name": "básico"}, headers=headers)
    assert duplicate_plan.status_code == 409
    updated = await client.put(f"/api/v1/catalog/services/{sid}/plans/{pid}", json={"name": "Pro"}, headers=headers)
    assert updated.status_code == 200
    deleted = await client.delete(f"/api/v1/catalog/services/{sid}", headers=headers)
    assert deleted.status_code == 204
    plans = await client.get(f"/api/v1/catalog/services/{sid}/plans", headers=headers)
    assert plans.status_code == 404


async def test_master_without_context_forbidden(client, master_user):
    headers = await _login(client, "master", "master-password")
    response = await client.get("/api/v1/catalog/services", headers=headers)
    assert response.status_code == 403


async def test_master_switched_context_can_manage_catalog(client, active_tenant_user, auth_headers, db_session):
    tenant_id = str(await _tenant_id(db_session, active_tenant_user))
    switched = await client.post("/api/v1/auth/switch-tenant", json={"tenant_id": tenant_id}, headers=auth_headers)
    assert switched.status_code == 200
    headers = {"Authorization": f"Bearer {switched.json()['access_token']}"}
    response = await client.post("/api/v1/catalog/services", json={"name": "Soporte"}, headers=headers)
    assert response.status_code == 201
