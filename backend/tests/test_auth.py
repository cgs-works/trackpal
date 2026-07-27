import asyncio
from datetime import datetime

import pytest
from sqlalchemy import select

import app.api.dependencies as dependencies
from app.core.config import settings
from app.core.security import create_access_token
from app.models import Tenant, User

pytestmark = pytest.mark.asyncio


async def test_login_success(client, master_user):
    response = await client.post(
        "/api/v1/auth/login",
        json={"username": "master", "password": "master-password"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["access_token"]
    assert body["refresh_token"]
    assert body["token_type"] == "bearer"
    assert body["user"]["username"] == master_user.username
    assert body["user"]["role"] == "master"


async def test_login_invalid_password(client, master_user):
    response = await client.post(
        "/api/v1/auth/login",
        json={"username": "master", "password": "wrong-password"},
    )

    assert response.status_code == 401


async def test_failed_demo_login_does_not_activate_tenant(
    client, db_session, pending_demo_user
):
    response = await client.post(
        "/api/v1/auth/login",
        json={"username": pending_demo_user.username, "password": "wrong-password"},
    )

    tenant = (
        await db_session.execute(
            select(Tenant).where(Tenant.owner_user_id == pending_demo_user.id)
        )
    ).scalar_one()
    assert response.status_code == 401
    assert tenant.demo_activated_at is None
    assert tenant.demo_expires_at is None


async def test_demo_login_activates_once_and_exposes_only_lifecycle_metadata(
    client, db_session, pending_demo_user
):
    first = await client.post(
        "/api/v1/auth/login",
        json={"username": pending_demo_user.username, "password": "demo-password"},
    )
    tenant = (
        await db_session.execute(
            select(Tenant).where(Tenant.owner_user_id == pending_demo_user.id)
        )
    ).scalar_one()
    activated_at = tenant.demo_activated_at
    expires_at = tenant.demo_expires_at

    second = await client.post(
        "/api/v1/auth/login",
        json={"username": pending_demo_user.username, "password": "demo-password"},
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert expires_at is not None and activated_at is not None
    assert (expires_at - activated_at).total_seconds() == 48 * 60 * 60
    assert second.json()["is_demo"] is True
    assert second.json()["tenant_plan"] == "starter"
    assert second.json()["demo_credentials_version"] == 1
    assert second.json()["demo_activated_at"] == first.json()["demo_activated_at"]
    assert second.json()["demo_expires_at"] == first.json()["demo_expires_at"]
    assert second.json()["server_time"]
    assert "workspace" not in second.json()


async def test_concurrent_demo_logins_share_one_activation_window(
    client, db_session, pending_demo_user
):
    demo_user_id = pending_demo_user.id
    responses = await asyncio.gather(
        client.post(
            "/api/v1/auth/login",
            json={"username": "pending-demo", "password": "demo-password"},
        ),
        client.post(
            "/api/v1/auth/login",
            json={"username": "pending-demo", "password": "demo-password"},
        ),
    )

    db_session.expire_all()
    tenant = (
        await db_session.execute(
            select(Tenant).where(Tenant.owner_user_id == demo_user_id)
        )
    ).scalar_one()
    assert all(response.status_code == 200 for response in responses)
    assert tenant.demo_activated_at is not None
    assert tenant.demo_expires_at is not None
    assert (tenant.demo_expires_at - tenant.demo_activated_at).total_seconds() == (
        48 * 60 * 60
    )
    assert len({response.json()["demo_expires_at"] for response in responses}) == 1


async def test_demo_heartbeat_returns_lifecycle_only_data(client, active_demo_user):
    login = await client.post(
        "/api/v1/auth/login",
        json={"username": active_demo_user.username, "password": "demo-password"},
    )
    response = await client.post(
        "/api/v1/auth/heartbeat",
        headers={"Authorization": f"Bearer {login.json()['access_token']}"},
    )

    assert response.status_code == 200
    assert response.json()["is_demo"] is True
    assert response.json()["demo_tenant_id"]
    assert response.json()["demo_name"] == "Active Demo"
    assert response.json()["demo_status"] == "active"
    assert response.json()["demo_credentials_version"] == 1
    assert set(response.json()) == {
        "is_demo",
        "demo_tenant_id",
        "demo_name",
        "tenant_plan",
        "demo_status",
        "demo_activated_at",
        "demo_expires_at",
        "demo_credentials_version",
        "server_time",
    }


async def test_demo_refresh_and_logout_preserve_lifecycle_window(
    client, db_session, active_demo_user
):
    demo_user_id = active_demo_user.id
    login = await client.post(
        "/api/v1/auth/login",
        json={"username": "active-demo", "password": "demo-password"},
    )
    db_session.expire_all()
    before = (
        await db_session.execute(
            select(Tenant).where(Tenant.owner_user_id == demo_user_id)
        )
    ).scalar_one()
    activated_at = before.demo_activated_at
    expires_at = before.demo_expires_at

    refreshed = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": login.json()["refresh_token"]},
    )
    logged_out = await client.post(
        "/api/v1/auth/logout",
        json={"refresh_token": refreshed.json()["refresh_token"]},
    )
    db_session.expire_all()
    after = (
        await db_session.execute(
            select(Tenant).where(Tenant.owner_user_id == demo_user_id)
        )
    ).scalar_one()

    assert refreshed.status_code == 200
    assert logged_out.status_code == 204
    assert after.demo_activated_at == activated_at
    assert after.demo_expires_at == expires_at


async def test_demo_password_replacement_revokes_old_sessions_without_extending_lifecycle(
    client, db_session, active_demo_user
):
    demo_user_id = active_demo_user.id
    login = await client.post(
        "/api/v1/auth/login",
        json={"username": active_demo_user.username, "password": "demo-password"},
    )
    old_access_token = login.json()["access_token"]
    old_refresh_token = login.json()["refresh_token"]
    tenant_before = (
        await db_session.execute(
            select(Tenant).where(Tenant.owner_user_id == demo_user_id)
        )
    ).scalar_one()
    activated_at = tenant_before.demo_activated_at
    expires_at = tenant_before.demo_expires_at

    changed = await client.put(
        "/api/v1/me/password",
        headers={"Authorization": f"Bearer {old_access_token}"},
        json={"old_password": "demo-password", "new_password": "new-demo-password"},
    )
    old_access = await client.get(
        "/api/v1/me", headers={"Authorization": f"Bearer {old_access_token}"}
    )
    old_refresh = await client.post(
        "/api/v1/auth/refresh", json={"refresh_token": old_refresh_token}
    )
    new_login = await client.post(
        "/api/v1/auth/login",
        json={"username": active_demo_user.username, "password": "new-demo-password"},
    )
    db_session.expire_all()
    tenant_after = (
        await db_session.execute(
            select(Tenant).where(Tenant.owner_user_id == demo_user_id)
        )
    ).scalar_one()

    assert changed.status_code == 200
    assert old_access.status_code == 401
    assert old_access.json()["detail"] == "demo_credentials_replaced"
    assert old_refresh.status_code == 401
    assert old_refresh.json()["detail"] == "demo_credentials_replaced"
    assert new_login.status_code == 200
    assert tenant_after.demo_credentials_version == 2
    assert tenant_after.demo_activated_at == activated_at
    assert tenant_after.demo_expires_at == expires_at


async def test_expired_demo_is_deleted_on_first_login_request(
    client, db_session, expired_demo_user
):
    demo_user_id = expired_demo_user.id
    response = await client.post(
        "/api/v1/auth/login",
        json={"username": expired_demo_user.username, "password": "demo-password"},
    )

    db_session.expire_all()
    user = await db_session.get(User, demo_user_id)
    tenant = (
        await db_session.execute(
            select(Tenant).where(Tenant.owner_user_id == demo_user_id)
        )
    ).scalar_one_or_none()
    assert response.status_code == 410
    assert response.json()["detail"] == "demo_ended"
    assert user is None
    assert tenant is None


async def test_production_heartbeat_has_no_demo_metadata(client, master_user):
    login = await client.post(
        "/api/v1/auth/login",
        json={"username": "master", "password": "master-password"},
    )
    response = await client.post(
        "/api/v1/auth/heartbeat",
        headers={"Authorization": f"Bearer {login.json()['access_token']}"},
    )

    assert response.status_code == 200
    assert response.json()["is_demo"] is False
    assert response.json()["demo_status"] is None
    datetime.fromisoformat(response.json()["server_time"].replace("Z", "+00:00"))


async def test_login_deactivated_tenant(client, deactivated_tenant_user):
    response = await client.post(
        "/api/v1/auth/login",
        json={"username": "inactive-tenant", "password": "tenant-password"},
    )

    assert response.status_code == 401


async def test_login_deactivated_tenant_is_rejected_after_profile_lookup(
    client, deactivated_tenant_user
):
    response = await client.post(
        "/api/v1/auth/login",
        json={"username": "inactive-tenant", "password": "tenant-password"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid credentials or account deactivated"


async def test_login_client_success(client, active_client_user):
    response = await client.post(
        "/api/v1/auth/login",
        json={"username": active_client_user.username, "password": "client-password"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["user"]["role"] == "client"
    assert body["active_tenant_id"]
    assert body["user"]["username"] == active_client_user.username


async def test_login_inactive_client_rejected(client, inactive_client_user):
    response = await client.post(
        "/api/v1/auth/login",
        json={"username": inactive_client_user.username, "password": "client-password"},
    )

    assert response.status_code == 401


async def test_login_client_under_inactive_tenant_rejected(
    client, active_client_user, active_tenant_user, auth_headers
):
    response = await client.patch(
        f"/api/v1/tenants/{active_tenant_user.id}/deactivate",
        headers=auth_headers,
    )
    assert response.status_code == 200

    login_response = await client.post(
        "/api/v1/auth/login",
        json={"username": active_client_user.username, "password": "client-password"},
    )

    assert login_response.status_code == 401


async def test_malformed_tenant_token_without_active_tenant_returns_401(
    client, active_tenant_user, monkeypatch
):
    async def raise_missing_context(*args, **kwargs):
        raise ValueError("active_tenant_id required for tenant RLS context")

    monkeypatch.setattr(dependencies, "set_rls_context", raise_missing_context)
    token = create_access_token(subject=str(active_tenant_user.id), role="tenant")

    response = await client.get(
        "/api/v1/me", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 401


async def test_malformed_client_token_without_active_tenant_returns_401(
    client, active_client_user
):
    token = create_access_token(subject=str(active_client_user.id), role="client")

    response = await client.get(
        "/api/v1/me", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 401


async def test_refresh_token(client, master_user):
    login_response = await client.post(
        "/api/v1/auth/login",
        json={"username": "master", "password": "master-password"},
    )
    refresh_token = login_response.json()["refresh_token"]

    response = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token},
    )

    assert response.status_code == 200
    assert response.json()["access_token"]
    assert response.json()["refresh_token"]


async def test_refresh_token_rotation(client, master_user):
    login_response = await client.post(
        "/api/v1/auth/login",
        json={"username": "master", "password": "master-password"},
    )
    old_refresh_token = login_response.json()["refresh_token"]

    first_refresh = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": old_refresh_token},
    )
    second_refresh = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": old_refresh_token},
    )

    assert first_refresh.status_code == 200
    assert second_refresh.status_code == 401


async def test_refresh_token_client(client, active_client_user):
    login_response = await client.post(
        "/api/v1/auth/login",
        json={"username": active_client_user.username, "password": "client-password"},
    )
    refresh_token = login_response.json()["refresh_token"]

    response = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token},
    )

    assert response.status_code == 200
    assert response.json()["active_tenant_id"]


async def test_refresh_token_client_under_inactive_tenant_rejected(
    client, active_client_user, active_tenant_user, auth_headers
):
    login_response = await client.post(
        "/api/v1/auth/login",
        json={"username": active_client_user.username, "password": "client-password"},
    )
    refresh_token = login_response.json()["refresh_token"]

    await client.patch(
        f"/api/v1/tenants/{active_tenant_user.id}/deactivate",
        headers=auth_headers,
    )

    response = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token},
    )

    assert response.status_code == 401


async def test_logout(client, master_user):
    login_response = await client.post(
        "/api/v1/auth/login",
        json={"username": "master", "password": "master-password"},
    )
    refresh_token = login_response.json()["refresh_token"]

    logout_response = await client.post(
        "/api/v1/auth/logout",
        json={"refresh_token": refresh_token},
    )
    refresh_response = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token},
    )

    assert logout_response.status_code == 204
    assert refresh_response.status_code == 401


async def test_identify_by_phone(client, master_user):
    response = await client.get(
        "/api/v1/integrations/n8n/identify",
        params={"phone": "+12015550001"},
        headers={"X-API-Key": settings.n8n_api_key},
    )

    assert response.status_code == 200
    assert response.json()["username"] == "master"
    assert response.json()["role"] == "master"


async def test_identify_by_phone_finds_active_tenant_with_api_key_context(
    client, active_tenant_user
):
    response = await client.get(
        "/api/v1/integrations/n8n/identify",
        params={"phone": "+12015550002"},
        headers={"X-API-Key": settings.n8n_api_key},
    )

    assert response.status_code == 200
    assert response.json()["username"] == "tenant"
    assert response.json()["role"] == "tenant"


async def test_identify_no_phone(client, master_user):
    response = await client.get(
        "/api/v1/integrations/n8n/identify",
        params={"phone": "+99999999999"},
        headers={"X-API-Key": settings.n8n_api_key},
    )

    assert response.status_code == 404


async def test_identify_invalid_api_key(client, master_user):
    response = await client.get(
        "/api/v1/integrations/n8n/identify",
        params={"phone": "+10000000000"},
        headers={"X-API-Key": "wrong-key"},
    )

    assert response.status_code == 401


async def test_refresh_token_as_bearer_fails(client, master_user):
    login_response = await client.post(
        "/api/v1/auth/login",
        json={"username": "master", "password": "master-password"},
    )
    refresh_token = login_response.json()["refresh_token"]

    response = await client.get(
        "/api/v1/tenants/",
        headers={"Authorization": f"Bearer {refresh_token}"},
    )

    assert response.status_code == 401


async def test_deactivated_tenant_old_access_token_fails(
    client, active_tenant_user, auth_headers
):
    login_response = await client.post(
        "/api/v1/auth/login",
        json={"username": "tenant", "password": "tenant-password"},
    )
    old_access_token = login_response.json()["access_token"]

    # Deactivate the tenant
    await client.patch(
        f"/api/v1/tenants/{active_tenant_user.id}/deactivate",
        headers=auth_headers,
    )

    # Old access token should be rejected
    response = await client.get(
        "/api/v1/me",
        headers={"Authorization": f"Bearer {old_access_token}"},
    )

    assert response.status_code == 401


async def test_deactivated_tenant_old_refresh_token_fails(
    client, active_tenant_user, auth_headers
):
    login_response = await client.post(
        "/api/v1/auth/login",
        json={"username": "tenant", "password": "tenant-password"},
    )
    old_refresh_token = login_response.json()["refresh_token"]

    # Deactivate the tenant
    await client.patch(
        f"/api/v1/tenants/{active_tenant_user.id}/deactivate",
        headers=auth_headers,
    )

    # Old refresh token should be rejected
    response = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": old_refresh_token},
    )

    assert response.status_code == 401


async def test_identify_deactivated_tenant(client, deactivated_tenant_user):
    response = await client.get(
        "/api/v1/integrations/n8n/identify",
        params={"phone": "+30000000000"},
        headers={"X-API-Key": settings.n8n_api_key},
    )

    assert response.status_code == 404


async def test_identify_plus_prefix_with_canonical_db(client, db_session, master_user):
    """Identify with + prefix works when DB stores canonical phone.

    Sets master's phone to canonical digits-only, then identifies
    with + prefix input.
    """
    from uuid import UUID
    from app.models import MasterProfile
    from sqlalchemy import select

    result = await db_session.execute(
        select(MasterProfile).where(MasterProfile.id == UUID(str(master_user.id)))
    )
    profile = result.scalar_one_or_none()
    profile.phone = "10000000000"
    await db_session.commit()

    response = await client.get(
        "/api/v1/integrations/n8n/identify",
        params={"phone": "+10000000000"},
        headers={"X-API-Key": settings.n8n_api_key},
    )

    assert response.status_code == 200
    assert response.json()["username"] == "master"
    assert response.json()["role"] == "master"


async def test_identify_jid_suffix_with_canonical_db(client, db_session, master_user):
    """JID suffix input identifies canonical DB phone."""
    from uuid import UUID
    from app.models import MasterProfile
    from sqlalchemy import select

    result = await db_session.execute(
        select(MasterProfile).where(MasterProfile.id == UUID(str(master_user.id)))
    )
    profile = result.scalar_one_or_none()
    profile.phone = "10000000000"
    await db_session.commit()

    response = await client.get(
        "/api/v1/integrations/n8n/identify",
        params={"phone": "10000000000@s.whatsapp.net"},
        headers={"X-API-Key": settings.n8n_api_key},
    )

    assert response.status_code == 200
    assert response.json()["username"] == "master"


async def test_identify_no_plus_with_canonical_db(client, db_session, master_user):
    """Phone without + prefix identifies canonical DB phone."""
    from uuid import UUID
    from app.models import MasterProfile
    from sqlalchemy import select

    result = await db_session.execute(
        select(MasterProfile).where(MasterProfile.id == UUID(str(master_user.id)))
    )
    profile = result.scalar_one_or_none()
    profile.phone = "10000000000"
    await db_session.commit()

    response = await client.get(
        "/api/v1/integrations/n8n/identify",
        params={"phone": "10000000000"},  # no + prefix
        headers={"X-API-Key": settings.n8n_api_key},
    )

    assert response.status_code == 200
    assert response.json()["username"] == "master"
    assert response.json()["role"] == "master"


async def test_identify_plus_jid_suffix_with_canonical_db(
    client, db_session, master_user
):
    """+ prefix + JID suffix identifies canonical DB phone."""
    from uuid import UUID
    from app.models import MasterProfile
    from sqlalchemy import select

    result = await db_session.execute(
        select(MasterProfile).where(MasterProfile.id == UUID(str(master_user.id)))
    )
    profile = result.scalar_one_or_none()
    profile.phone = "10000000000"
    await db_session.commit()

    response = await client.get(
        "/api/v1/integrations/n8n/identify",
        params={"phone": "+10000000000@s.whatsapp.net"},
        headers={"X-API-Key": settings.n8n_api_key},
    )

    assert response.status_code == 200
    assert response.json()["username"] == "master"


async def test_identify_plus_prefix_finds_prefixed_db(client, master_user):
    """+ prefix input still finds DB phone with + prefix (pre-migration)."""
    response = await client.get(
        "/api/v1/integrations/n8n/identify",
        params={"phone": "+12015550001"},
        headers={"X-API-Key": settings.n8n_api_key},
    )

    assert response.status_code == 200
    assert response.json()["username"] == "master"
