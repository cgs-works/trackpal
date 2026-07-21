from datetime import datetime

import pytest
from sqlalchemy import select

from app.core.security import create_access_token
from app.models import Tenant, TenantHelpAcknowledgement

pytestmark = pytest.mark.asyncio


async def _login(client, username: str, password: str) -> dict[str, str]:
    response = await client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": password},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


async def _set_tenant_plan(db_session, user_id, plan: str) -> None:
    tenant = (
        await db_session.execute(select(Tenant).where(Tenant.owner_user_id == user_id))
    ).scalar_one()
    tenant.plan = plan
    await db_session.commit()


async def test_tenant_admin_receives_unseen_tracer_and_can_complete_idempotently(
    client, active_tenant_user, db_session
):
    await _set_tenant_plan(db_session, active_tenant_user.id, "starter")
    headers = await _login(client, "tenant", "tenant-password")

    unseen = await client.get("/api/v1/help/tour", headers=headers)

    assert unseen.status_code == 200
    release = unseen.json()
    assert release["release_id"] == "tenant-admin-starter-1"
    assert release["status"] is None
    assert [step["target"] for step in release["steps"]] == [
        "admin.dashboard",
        "admin.dashboard",
        "admin.settings.profile",
        "admin.settings.whatsapp",
        "admin.settings.code-services",
        "admin.settings.access-control",
        "admin.help",
    ]
    assert all(step["content"] for step in release["steps"])

    acknowledged = await client.post(
        "/api/v1/help/tour/tenant-admin-starter-1/acknowledge",
        headers=headers,
        json={"status": "completed"},
    )
    repeated = await client.post(
        "/api/v1/help/tour/tenant-admin-starter-1/acknowledge",
        headers=headers,
        json={"status": "completed"},
    )

    assert acknowledged.status_code == 200
    assert repeated.status_code == 200
    assert acknowledged.json() == repeated.json()
    assert acknowledged.json()["status"] == "completed"
    assert datetime.fromisoformat(acknowledged.json()["acknowledged_at"])

    no_longer_unseen = await client.get("/api/v1/help/tour", headers=headers)
    replay = await client.get(
        "/api/v1/help/tour/tenant-admin-starter-1/replay", headers=headers
    )

    assert no_longer_unseen.status_code == 404
    assert replay.status_code == 200
    assert replay.json()["status"] == "completed"

    rows = (
        (
            await db_session.execute(
                select(TenantHelpAcknowledgement).where(
                    TenantHelpAcknowledgement.release_id == "tenant-admin-starter-1"
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(rows) == 1


async def test_skip_is_confirmed_by_the_client_and_replay_remains_available(
    client, active_tenant_user, db_session
):
    await _set_tenant_plan(db_session, active_tenant_user.id, "starter")
    headers = await _login(client, "tenant", "tenant-password")

    skipped = await client.post(
        "/api/v1/help/tour/tenant-admin-starter-1/acknowledge",
        headers=headers,
        json={"status": "skipped"},
    )
    replay = await client.get(
        "/api/v1/help/tour/tenant-admin-starter-1/replay", headers=headers
    )

    assert skipped.status_code == 200
    assert skipped.json()["status"] == "skipped"
    assert replay.status_code == 200
    assert replay.json()["status"] == "skipped"


async def test_starter_release_is_not_eligible_for_pro_tenants(
    client, active_tenant_user
):
    headers = await _login(client, "tenant", "tenant-password")

    unseen = await client.get("/api/v1/help/tour", headers=headers)
    replay = await client.get(
        "/api/v1/help/tour/tenant-admin-starter-1/replay", headers=headers
    )

    assert unseen.status_code == 404
    assert replay.status_code == 404


async def test_tour_is_private_to_tenant_admin_context(
    client, active_client_user, master_user, active_tenant_user, db_session
):
    unauthenticated = await client.get("/api/v1/help/tour")
    client_headers = await _login(
        client, active_client_user.username, "client-password"
    )
    client_response = await client.get("/api/v1/help/tour", headers=client_headers)

    tenant = (
        await db_session.execute(
            select(Tenant).where(Tenant.owner_user_id == active_tenant_user.id)
        )
    ).scalar_one()

    support_token = create_access_token(
        subject=str(master_user.id),
        role="master",
        active_tenant_id=str(tenant.id),
    )
    master_response = await client.get(
        "/api/v1/help/tour",
        headers={"Authorization": f"Bearer {support_token}"},
    )

    assert unauthenticated.status_code == 401
    assert client_response.status_code == 404
    assert master_response.status_code == 404
