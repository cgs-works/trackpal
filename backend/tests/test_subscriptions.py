import pytest
from datetime import date, datetime, timezone, timedelta
from cryptography.fernet import Fernet
import uuid

from app.core.config import settings
from app.core.encryption import (
    validate_encryption_key,
    encrypt_value,
    decrypt_value,
    get_fernet,
)
from app.models.subscription import (
    Subscription,
    SubscriptionEvent,
    SubscriptionReminderLog,
    SubscriptionReminderSettings,
)
from app.models.client import Client
from app.models.service import Service
from app.models.plan import Plan
from app.models.tenant import Tenant
from app.models.user import User
from app.core.config import settings
from app.core.errors import UserFacingError
from app.core.security import get_password_hash


def test_validate_encryption_key_success():
    # settings.data_encryption_key is currently a valid key set in conftest
    validate_encryption_key()


def test_validate_encryption_key_missing(monkeypatch):
    monkeypatch.setattr(settings, "data_encryption_key", "")
    with pytest.raises(ValueError, match="DATA_ENCRYPTION_KEY is not set"):
        validate_encryption_key()


def test_validate_encryption_key_invalid(monkeypatch):
    monkeypatch.setattr(settings, "data_encryption_key", "invalid-key-not-base64")
    with pytest.raises(ValueError, match="DATA_ENCRYPTION_KEY is invalid"):
        validate_encryption_key()


def test_encryption_reversibility():
    original = "MySecretPassword123!"
    encrypted = encrypt_value(original)
    assert encrypted != original
    assert encrypted is not None

    decrypted = decrypt_value(encrypted)
    assert decrypted == original


def test_encryption_handles_none():
    assert encrypt_value(None) is None
    assert decrypt_value(None) is None


@pytest.mark.asyncio
async def test_subscription_model_persistence(db_session, active_tenant_user):
    # Setup dependencies: Tenant, Client, Service, Plan
    # active_tenant_user fixture already creates a user and a tenant
    from sqlalchemy import select

    res = await db_session.execute(
        select(Tenant).where(Tenant.owner_user_id == active_tenant_user.id)
    )
    tenant = res.scalar_one()

    # Create a client
    client_user = User(
        username="sub_client1",
        password_hash=get_password_hash("client-password"),
        role="client",
    )
    db_session.add(client_user)
    await db_session.flush()
    client = Client(
        tenant_id=tenant.id,
        owner_user_id=client_user.id,
        full_name="Subscription Client",
        username=client_user.username,
        phone="+12015559999",
        is_active=True,
    )
    db_session.add(client)

    # Create a service
    service = Service(
        tenant_id=tenant.id,
        name="Netflix 4K",
    )
    db_session.add(service)
    await db_session.flush()

    # Create a plan
    plan = Plan(
        tenant_id=tenant.id,
        service_id=service.id,
        name="1 Screen",
    )
    db_session.add(plan)
    await db_session.flush()

    # Create subscription
    sub = Subscription(
        tenant_id=tenant.id,
        client_id=client.id,
        service_id=service.id,
        plan_id=plan.id,
        streaming_email="netflix_user@example.com",
        streaming_password_encrypted=encrypt_value("super_secret_netflix"),
        profile_name="Kids Profile",
        profile_pin_encrypted=encrypt_value("1234"),
        duration_type="1_month",
        starts_at=datetime.now(timezone.utc),
        expires_at=datetime.now(timezone.utc) + timedelta(days=30),
        status="active",
    )
    db_session.add(sub)
    await db_session.commit()

    # Query back and verify
    await db_session.refresh(sub)
    assert sub.id is not None
    assert sub.streaming_email == "netflix_user@example.com"
    assert decrypt_value(sub.streaming_password_encrypted) == "super_secret_netflix"
    assert sub.profile_name == "Kids Profile"
    assert decrypt_value(sub.profile_pin_encrypted) == "1234"
    assert sub.duration_type == "1_month"
    assert sub.status == "active"
    assert sub.created_at is not None
    assert sub.updated_at is not None

    # Test relationship
    assert sub.client.full_name == "Subscription Client"
    assert sub.service.name == "Netflix 4K"
    assert sub.plan.name == "1 Screen"


@pytest.mark.asyncio
async def test_subscription_event_model(db_session, active_tenant_user):
    from sqlalchemy import select

    res = await db_session.execute(
        select(Tenant).where(Tenant.owner_user_id == active_tenant_user.id)
    )
    tenant = res.scalar_one()

    # Minimal Subscription setup
    client_user = User(username="evt_client", password_hash="hash", role="client")
    db_session.add(client_user)
    await db_session.flush()
    client = Client(
        tenant_id=tenant.id,
        owner_user_id=client_user.id,
        full_name="Evt Client",
        username=client_user.username,
        is_active=True,
    )
    db_session.add(client)
    service = Service(tenant_id=tenant.id, name="Netflix")
    db_session.add(service)
    await db_session.flush()
    plan = Plan(tenant_id=tenant.id, service_id=service.id, name="Plan")
    db_session.add(plan)
    await db_session.flush()

    sub = Subscription(
        tenant_id=tenant.id,
        client_id=client.id,
        service_id=service.id,
        plan_id=plan.id,
        streaming_email="evt@example.com",
        duration_type="3_months",
        starts_at=datetime.now(timezone.utc),
        expires_at=datetime.now(timezone.utc) + timedelta(days=90),
        status="active",
    )
    db_session.add(sub)
    await db_session.flush()

    # Create subscription event
    event = SubscriptionEvent(
        tenant_id=tenant.id,
        subscription_id=sub.id,
        event_type="created",
        notes="First subscription creation event",
        event_metadata={"agent": "system", "reason": "user_action"},
    )
    db_session.add(event)
    await db_session.commit()

    # Query back and check
    await db_session.refresh(event)
    assert event.id is not None
    assert event.event_type == "created"
    assert event.notes == "First subscription creation event"
    assert event.event_metadata == {"agent": "system", "reason": "user_action"}
    assert event.subscription.streaming_email == "evt@example.com"


@pytest.mark.asyncio
async def test_subscription_reminder_log(db_session, active_tenant_user):
    from sqlalchemy import select

    res = await db_session.execute(
        select(Tenant).where(Tenant.owner_user_id == active_tenant_user.id)
    )
    tenant = res.scalar_one()

    # Minimal setup
    client_user = User(username="rem_client", password_hash="hash", role="client")
    db_session.add(client_user)
    await db_session.flush()
    client = Client(
        tenant_id=tenant.id,
        owner_user_id=client_user.id,
        full_name="Rem Client",
        username=client_user.username,
        is_active=True,
    )
    db_session.add(client)
    service = Service(tenant_id=tenant.id, name="Netflix")
    db_session.add(service)
    await db_session.flush()
    plan = Plan(tenant_id=tenant.id, service_id=service.id, name="Plan")
    db_session.add(plan)
    await db_session.flush()

    sub = Subscription(
        tenant_id=tenant.id,
        client_id=client.id,
        service_id=service.id,
        plan_id=plan.id,
        streaming_email="rem@example.com",
        duration_type="custom",
        starts_at=datetime.now(timezone.utc),
        expires_at=datetime.now(timezone.utc) + timedelta(days=15),
        status="active",
    )
    db_session.add(sub)
    await db_session.flush()

    # Create reminder log
    log = SubscriptionReminderLog(
        tenant_id=tenant.id,
        subscription_id=sub.id,
        recipient_type="client",
        recipient_phone="+12015551111",
        days_before_expiry=7,
        sent_for_date=date.today(),
        status="sent",
        attempt_count=1,
        sent_at=datetime.now(timezone.utc),
    )
    db_session.add(log)
    await db_session.commit()

    # Query back and verify
    await db_session.refresh(log)
    assert log.id is not None
    assert log.recipient_type == "client"
    assert log.recipient_phone == "+12015551111"
    assert log.days_before_expiry == 7
    assert log.sent_for_date == date.today()
    assert log.status == "sent"
    assert log.attempt_count == 1
    assert log.sent_at is not None


@pytest.mark.asyncio
async def test_subscription_reminder_settings(db_session, active_tenant_user):
    from sqlalchemy import select

    res = await db_session.execute(
        select(Tenant).where(Tenant.owner_user_id == active_tenant_user.id)
    )
    tenant = res.scalar_one()

    # Create settings
    settings_obj = SubscriptionReminderSettings(
        tenant_id=tenant.id,
        # checking default semantics: timezone=UTC, warning_days=[7,3,1], reminder_time="09:00", recipient_mode="tenant_only"
    )
    db_session.add(settings_obj)
    await db_session.commit()

    # Query back and verify defaults
    await db_session.refresh(settings_obj)
    assert settings_obj.id is not None
    assert settings_obj.tenant_id == tenant.id
    assert settings_obj.timezone == "UTC"
    assert settings_obj.warning_days == [7, 3, 1]
    assert settings_obj.reminder_time == "09:00"
    assert settings_obj.recipient_mode == "tenant_only"


async def _login_headers(async_client, username: str, password: str) -> dict[str, str]:
    response = await async_client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": password},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


async def _tenant_for_user(db_session, user: User) -> Tenant:
    from sqlalchemy import select

    result = await db_session.execute(
        select(Tenant).where(Tenant.owner_user_id == user.id)
    )
    return result.scalar_one()


async def _create_subscription_dependencies(
    db_session, tenant: Tenant, suffix: str = "api"
):
    client_user = User(
        username=f"{suffix}_client_user",
        password_hash=get_password_hash("client-password"),
        role="client",
    )
    db_session.add(client_user)
    await db_session.flush()
    client = Client(
        tenant_id=tenant.id,
        owner_user_id=client_user.id,
        full_name=f"{suffix.title()} Client",
        username=client_user.username,
        phone=f"+1201555{len(suffix):04d}",
        is_active=True,
    )
    service = Service(tenant_id=tenant.id, name=f"{suffix.title()} Service")
    db_session.add_all([client, service])
    await db_session.flush()
    plan = Plan(
        tenant_id=tenant.id, service_id=service.id, name=f"{suffix.title()} Plan"
    )
    db_session.add(plan)
    await db_session.commit()
    return client, service, plan


def _subscription_payload(client: Client, service: Service, plan: Plan, **overrides):
    payload = {
        "client_id": str(client.id),
        "service_id": str(service.id),
        "plan_id": str(plan.id),
        "streaming_email": "account@example.com",
        "streaming_password": "stream-secret",
        "profile_name": "Principal",
        "profile_pin": "1234",
        "duration_type": "1_month",
        "starts_at": datetime(2026, 1, 1, tzinfo=timezone.utc).isoformat(),
    }
    payload.update(overrides)
    return payload


@pytest.mark.asyncio
async def test_subscription_api_create_masks_secrets(
    client, db_session, active_tenant_user
):
    tenant = await _tenant_for_user(db_session, active_tenant_user)
    sub_client, service, plan = await _create_subscription_dependencies(
        db_session, tenant, "createapi"
    )
    headers = await _login_headers(client, "tenant", "tenant-password")

    response = await client.post(
        "/api/v1/subscriptions",
        json=_subscription_payload(sub_client, service, plan),
        headers=headers,
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["streaming_email"] == "account@example.com"
    assert body["has_password"] is True
    assert body["has_pin"] is True
    assert "streaming_password" not in body
    assert "streaming_password_encrypted" not in body
    assert "profile_pin" not in body
    assert "profile_pin_encrypted" not in body


@pytest.mark.asyncio
async def test_subscription_api_rejects_pin_without_profile(
    client, db_session, active_tenant_user
):
    tenant = await _tenant_for_user(db_session, active_tenant_user)
    sub_client, service, plan = await _create_subscription_dependencies(
        db_session, tenant, "pinapi"
    )
    headers = await _login_headers(client, "tenant", "tenant-password")

    response = await client.post(
        "/api/v1/subscriptions",
        json=_subscription_payload(
            sub_client, service, plan, profile_name=None, profile_pin="1234"
        ),
        headers=headers,
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_subscription_api_rejects_plan_service_mismatch(
    client, db_session, active_tenant_user
):
    tenant = await _tenant_for_user(db_session, active_tenant_user)
    sub_client, service, plan = await _create_subscription_dependencies(
        db_session, tenant, "mismatchapi"
    )
    other_service = Service(tenant_id=tenant.id, name="Other Service")
    db_session.add(other_service)
    await db_session.commit()
    headers = await _login_headers(client, "tenant", "tenant-password")

    response = await client.post(
        "/api/v1/subscriptions",
        json=_subscription_payload(sub_client, other_service, plan),
        headers=headers,
    )

    assert response.status_code == 409
    assert "plan not found" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_subscription_api_lifecycle_and_cancelled_filter(
    client, db_session, active_tenant_user
):
    tenant = await _tenant_for_user(db_session, active_tenant_user)
    sub_client, service, plan = await _create_subscription_dependencies(
        db_session, tenant, "lifeapi"
    )
    headers = await _login_headers(client, "tenant", "tenant-password")

    create_response = await client.post(
        "/api/v1/subscriptions",
        json=_subscription_payload(sub_client, service, plan),
        headers=headers,
    )
    assert create_response.status_code == 201, create_response.text
    subscription_id = create_response.json()["id"]

    renew_response = await client.post(
        f"/api/v1/subscriptions/{subscription_id}/renew",
        json={"duration_type": "3_months"},
        headers=headers,
    )
    assert renew_response.status_code == 200, renew_response.text
    assert renew_response.json()["duration_type"] == "3_months"

    cancel_response = await client.post(
        f"/api/v1/subscriptions/{subscription_id}/cancel",
        json={"notes": "cancel test"},
        headers=headers,
    )
    assert cancel_response.status_code == 200, cancel_response.text
    assert cancel_response.json()["status"] == "cancelled"
    assert cancel_response.json()["cancelled_at"] is not None

    default_list_response = await client.get("/api/v1/subscriptions", headers=headers)
    assert default_list_response.status_code == 200
    assert default_list_response.json() == []

    cancelled_list_response = await client.get(
        "/api/v1/subscriptions?status=cancelled",
        headers=headers,
    )
    assert cancelled_list_response.status_code == 200
    assert [item["id"] for item in cancelled_list_response.json()] == [subscription_id]

    reactivate_response = await client.post(
        f"/api/v1/subscriptions/{subscription_id}/reactivate",
        json={"duration_type": "1_month"},
        headers=headers,
    )
    assert reactivate_response.status_code == 200, reactivate_response.text
    assert reactivate_response.json()["status"] == "active"
    assert reactivate_response.json()["cancelled_at"] is None


@pytest.mark.asyncio
async def test_subscription_api_settings_defaults(client, active_tenant_user):
    headers = await _login_headers(client, "tenant", "tenant-password")

    response = await client.get("/api/v1/subscription-settings", headers=headers)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["timezone"] == "UTC"
    assert body["warning_days"] == [7, 3, 1]
    assert body["reminder_time"] == "09:00"
    assert body["recipient_mode"] == "tenant_only"


@pytest.mark.asyncio
async def test_subscription_api_reveal_credentials(
    client, db_session, active_tenant_user
):
    tenant = await _tenant_for_user(db_session, active_tenant_user)
    sub_client, service, plan = await _create_subscription_dependencies(
        db_session, tenant, "revealapi"
    )
    headers = await _login_headers(client, "tenant", "tenant-password")

    # 1. Create subscription with password and PIN
    payload = _subscription_payload(
        sub_client,
        service,
        plan,
        streaming_password="my-super-secret-password-123",
        profile_pin="5678",
    )
    create_res = await client.post(
        "/api/v1/subscriptions",
        json=payload,
        headers=headers,
    )
    assert create_res.status_code == 201
    sub_data = create_res.json()
    subscription_id = sub_data["id"]

    # Verify that the normal creation response does NOT return the plaintext values
    assert sub_data["has_password"] is True
    assert sub_data["has_pin"] is True
    assert "streaming_password" not in sub_data
    assert "profile_pin" not in sub_data

    # Verify that get subscription detail response does NOT return plaintext values either
    get_res = await client.get(
        f"/api/v1/subscriptions/{subscription_id}",
        headers=headers,
    )
    assert get_res.status_code == 200
    get_data = get_res.json()
    assert get_data["has_password"] is True
    assert get_data["has_pin"] is True
    assert "streaming_password" not in get_data
    assert "profile_pin" not in get_data

    # Fetch initial events count
    events_res = await client.get(
        f"/api/v1/subscriptions/{subscription_id}/events",
        headers=headers,
    )
    assert events_res.status_code == 200
    initial_events_count = len(events_res.json())

    # 2. Reveal credentials - Success
    reveal_res = await client.get(
        f"/api/v1/subscriptions/{subscription_id}/reveal",
        headers=headers,
    )
    assert reveal_res.status_code == 200
    reveal_data = reveal_res.json()
    assert reveal_data["streaming_password"] == "my-super-secret-password-123"
    assert reveal_data["profile_pin"] == "5678"

    # 3. Verify that revealing credentials did NOT create any subscription history events
    events_res_after = await client.get(
        f"/api/v1/subscriptions/{subscription_id}/events",
        headers=headers,
    )
    assert events_res_after.status_code == 200
    assert len(events_res_after.json()) == initial_events_count

    # 4. Create another subscription with None password/PIN
    payload_none = _subscription_payload(
        sub_client,
        service,
        plan,
        streaming_password=None,
        profile_pin=None,
        profile_name=None,
    )
    create_none_res = await client.post(
        "/api/v1/subscriptions",
        json=payload_none,
        headers=headers,
    )
    assert create_none_res.status_code == 201
    sub_none_id = create_none_res.json()["id"]

    reveal_none_res = await client.get(
        f"/api/v1/subscriptions/{sub_none_id}/reveal",
        headers=headers,
    )
    assert reveal_none_res.status_code == 200
    reveal_none_data = reveal_none_res.json()
    assert reveal_none_data["streaming_password"] is None
    assert reveal_none_data["profile_pin"] is None


@pytest.mark.asyncio
async def test_subscription_api_reveal_credentials_unauthorized_and_cross_tenant(
    client, db_session, active_tenant_user
):
    # Setup Tenant A (active_tenant_user)
    tenant_a = await _tenant_for_user(db_session, active_tenant_user)
    sub_client_a, service_a, plan_a = await _create_subscription_dependencies(
        db_session, tenant_a, "revealcrossa"
    )
    headers_a = await _login_headers(client, "tenant", "tenant-password")

    # Create subscription in Tenant A
    payload_a = _subscription_payload(
        sub_client_a,
        service_a,
        plan_a,
        streaming_password="tenant-a-secret",
        profile_pin="1111",
    )
    create_res = await client.post(
        "/api/v1/subscriptions",
        json=payload_a,
        headers=headers_a,
    )
    assert create_res.status_code == 201
    subscription_id = create_res.json()["id"]

    # Setup Tenant B (another user)
    user_b = User(
        username="tenant-b",
        password_hash=get_password_hash("tenant-b-password"),
        role="tenant",
    )
    db_session.add(user_b)
    await db_session.flush()
    tenant_b = Tenant(
        owner_user_id=user_b.id,
        client_prefix="tnc01",
        name="Tenant B",
        whatsapp_phone="+12015550005",
        is_active=True,
    )
    db_session.add(tenant_b)
    await db_session.commit()

    headers_b = await _login_headers(client, "tenant-b", "tenant-b-password")

    # Attempt to reveal Tenant A's subscription using Tenant B's credentials -> Should return 404
    cross_res = await client.get(
        f"/api/v1/subscriptions/{subscription_id}/reveal",
        headers=headers_b,
    )
    assert cross_res.status_code == 404

    # Setup a Client user belonging to Tenant A -> Should return 403 (Unauthorized role)
    client_user = User(
        username="tenant_a_client_user",
        password_hash=get_password_hash("client-password"),
        role="client",
    )
    db_session.add(client_user)
    await db_session.flush()
    db_session.add(
        Client(
            tenant_id=tenant_a.id,
            owner_user_id=client_user.id,
            full_name="Client Role User",
            username=client_user.username,
            phone="+12015551234",
            is_active=True,
        )
    )
    await db_session.commit()

    headers_client = await _login_headers(
        client, "tenant_a_client_user", "client-password"
    )

    client_res = await client.get(
        f"/api/v1/subscriptions/{subscription_id}/reveal",
        headers=headers_client,
    )
    assert client_res.status_code == 403


@pytest.mark.asyncio
async def test_subscription_job_endpoint_requires_api_key(client):
    """Job endpoint returns 401 without valid X-API-Key header."""
    resp = await client.post("/api/v1/subscriptions/jobs?task=cleanup")
    assert resp.status_code == 401
    assert "Invalid API Key" in resp.text or "api" in resp.text.lower()

    # Wrong key
    resp = await client.post(
        "/api/v1/subscriptions/jobs?task=cleanup",
        headers={"X-API-Key": "wrong-key"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_subscription_job_endpoint_invalid_task(client):
    """Job endpoint returns 400 for invalid task parameter."""
    api_key = settings.n8n_api_key
    resp = await client.post(
        "/api/v1/subscriptions/jobs?task=invalid_task",
        headers={"X-API-Key": api_key},
    )
    assert resp.status_code == 400
    assert "Invalid task" in resp.text


@pytest.mark.asyncio
async def test_subscription_job_endpoint_cleanup(
    client, db_session, active_tenant_user
):
    """Cleanup job transitions expired active subs, cancels long-expired, and deletes old cancelled."""
    from sqlalchemy import select

    api_key = settings.n8n_api_key
    tenant = await _tenant_for_user(db_session, active_tenant_user)

    # Create subscriptions in various states
    sub_client, service, plan = await _create_subscription_dependencies(
        db_session, tenant, "cleanup"
    )

    headers = await _login_headers(client, "tenant", "tenant-password")

    now = datetime.now(timezone.utc)

    # 1. Active subscription already past expires_at → should become expired
    past_date = (now - timedelta(days=2)).isoformat()
    resp1 = await client.post(
        "/api/v1/subscriptions",
        json=_subscription_payload(
            sub_client,
            service,
            plan,
            streaming_password="p1",
            profile_pin=None,
            profile_name=None,
            duration_type="custom",
            starts_at=(now - timedelta(days=10)).isoformat(),
            expires_at=past_date,
        ),
        headers=headers,
    )
    assert resp1.status_code == 201
    sub1_id = resp1.json()["id"]

    # 2. Subscription already expired for 7+ days → should become cancelled
    resp2 = await client.post(
        "/api/v1/subscriptions",
        json=_subscription_payload(
            sub_client,
            service,
            plan,
            streaming_password="p2",
            profile_pin=None,
            profile_name=None,
            duration_type="custom",
            starts_at=(now - timedelta(days=30)).isoformat(),
            expires_at=(now - timedelta(days=10)).isoformat(),
        ),
        headers=headers,
    )
    assert resp2.status_code == 201
    sub2_id = resp2.json()["id"]
    # Manually set to expired (job transition will test expired→cancelled for sub2)
    await client.patch(
        f"/api/v1/subscriptions/{sub2_id}/cancel",
        json={"notes": "manual cancel for expired"},
        headers=headers,
    )

    # Manually expire sub2 to test expired→cancelled path
    res = await db_session.execute(
        select(Subscription).where(Subscription.id == uuid.UUID(sub2_id))
    )
    sub2 = res.scalar_one()
    sub2.status = "expired"
    sub2.expires_at = now - timedelta(days=10)
    await db_session.commit()

    # 3. Subscription cancelled for 30+ days → should be deleted
    resp3 = await client.post(
        "/api/v1/subscriptions",
        json=_subscription_payload(
            sub_client,
            service,
            plan,
            streaming_password="p3",
            profile_pin=None,
            profile_name=None,
            duration_type="custom",
            starts_at=(now - timedelta(days=60)).isoformat(),
            expires_at=(now - timedelta(days=35)).isoformat(),
        ),
        headers=headers,
    )
    assert resp3.status_code == 201
    sub3_id = resp3.json()["id"]
    # Cancel it first
    await client.post(
        f"/api/v1/subscriptions/{sub3_id}/cancel",
        json={"notes": "manual cancel"},
        headers=headers,
    )
    # Backdate cancelled_at beyond 30 days
    res3 = await db_session.execute(
        select(Subscription).where(Subscription.id == uuid.UUID(sub3_id))
    )
    sub3 = res3.scalar_one()
    sub3.status = "cancelled"
    sub3.cancelled_at = now - timedelta(days=35)
    await db_session.commit()

    # Run cleanup job
    resp = await client.post(
        "/api/v1/subscriptions/jobs?task=cleanup",
        headers={"X-API-Key": api_key},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["task"] == "cleanup"
    assert data["items_processed"] >= 3

    # Verify results have expected actions
    actions = {r["action"] for r in data["results"] if r["status"] == "success"}
    assert "expire" in actions
    assert "cancel_expired" in actions
    assert "delete_cancelled" in actions

    # No PII or secrets in results — results contain only IDs, actions, status, error
    for r in data["results"]:
        assert isinstance(r.get("id"), str)
        assert r["action"] in ("expire", "cancel_expired", "delete_cancelled")

    # Verify sub1 is now expired
    resp1_get = await client.get(f"/api/v1/subscriptions/{sub1_id}", headers=headers)
    assert resp1_get.status_code == 200
    assert resp1_get.json()["status"] == "expired"

    # Verify sub2 is now cancelled
    resp2_get = await client.get(f"/api/v1/subscriptions/{sub2_id}", headers=headers)
    assert resp2_get.status_code == 200
    assert resp2_get.json()["status"] == "cancelled"
    assert resp2_get.json()["cancelled_at"] is not None

    # Verify sub3 is deleted (404)
    resp3_get = await client.get(f"/api/v1/subscriptions/{sub3_id}", headers=headers)
    assert resp3_get.status_code == 404


@pytest.mark.asyncio
async def test_subscription_job_endpoint_reminders_stub(client):
    """Reminders task returns empty results (separate TODO)."""
    api_key = settings.n8n_api_key
    resp = await client.post(
        "/api/v1/subscriptions/jobs?task=reminders",
        headers={"X-API-Key": api_key},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["task"] == "reminders"
    assert data["items_processed"] == 0
    assert data["results"] == []


@pytest.mark.asyncio
async def test_subscription_job_endpoint_all(client, db_session, active_tenant_user):
    """'all' task runs both cleanup and reminders."""
    api_key = settings.n8n_api_key
    resp = await client.post(
        "/api/v1/subscriptions/jobs?task=all",
        headers={"X-API-Key": api_key},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["task"] == "all"
    assert "results" in data


@pytest.mark.asyncio
async def test_subscription_reminder_pending_endpoint(
    client, db_session, active_tenant_user
):
    """Reminder pending endpoint generates and returns payloads."""
    from datetime import datetime, timezone, timedelta
    from sqlalchemy import select

    api_key = settings.n8n_api_key
    tenant = await _tenant_for_user(db_session, active_tenant_user)
    sub_client, service, plan = await _create_subscription_dependencies(
        db_session, tenant, "remind"
    )

    now = datetime.now(timezone.utc)

    # Create an active subscription that expires in 7 days (matching default warning_days)
    headers = await _login_headers(client, "tenant", "tenant-password")
    resp = await client.post(
        "/api/v1/subscriptions",
        json=_subscription_payload(
            sub_client,
            service,
            plan,
            streaming_password="pwd1",
            profile_pin=None,
            profile_name=None,
            duration_type="custom",
            starts_at=now.isoformat(),
            expires_at=(now + timedelta(days=7)).isoformat(),
        ),
        headers=headers,
    )
    assert resp.status_code == 201
    sub_id = resp.json()["id"]

    # Set reminder_time to 00:00 so it passes regardless of current time
    await client.put(
        "/api/v1/subscription-settings",
        json={"reminder_time": "00:00"},
        headers=headers,
    )

    # Fetch pending reminders
    resp_pending = await client.post(
        "/api/v1/subscriptions/reminders/pending",
        headers={"X-API-Key": api_key},
    )
    assert resp_pending.status_code == 200
    data = resp_pending.json()
    assert "items" in data
    assert "next_cursor" in data
    assert len(data["items"]) >= 1

    # Verify payload structure
    payload = data["items"][0]
    assert "id" in payload
    assert payload["subscription_id"] == sub_id
    assert payload["days_before_expiry"] == 7
    assert "message" in payload
    assert "⚠️" in payload["message"]
    assert service.name in payload["message"]
    assert payload["recipient_type"] == "tenant"
    assert payload.get("evolution_instance_name") is not None

    # Same call again should not duplicate (deduped by unique constraint)
    resp_pending2 = await client.post(
        "/api/v1/subscriptions/reminders/pending",
        headers={"X-API-Key": api_key},
    )
    assert resp_pending2.status_code == 200
    data2 = resp_pending2.json()
    # Verify no NEW reminder logs were created (existing one has same id)
    existing_ids = {item["id"] for item in data["items"]}
    new_ids = {item["id"] for item in data2["items"]}
    assert new_ids.issubset(existing_ids), "Second call created duplicate reminder logs"


@pytest.mark.asyncio
async def test_subscription_reminder_mark_sent(client, db_session, active_tenant_user):
    """Mark-sent updates status and records sent_at."""
    from datetime import datetime, timezone, timedelta

    api_key = settings.n8n_api_key
    tenant = await _tenant_for_user(db_session, active_tenant_user)
    sub_client, service, plan = await _create_subscription_dependencies(
        db_session, tenant, "marksent"
    )

    now = datetime.now(timezone.utc)
    headers = await _login_headers(client, "tenant", "tenant-password")
    resp = await client.post(
        "/api/v1/subscriptions",
        json=_subscription_payload(
            sub_client,
            service,
            plan,
            streaming_password="pwd",
            profile_pin=None,
            profile_name=None,
            duration_type="custom",
            starts_at=now.isoformat(),
            expires_at=(now + timedelta(days=7)).isoformat(),
        ),
        headers=headers,
    )
    assert resp.status_code == 201

    # Set reminder_time to 00:00 so pending endpoint returns reminders
    await client.put(
        "/api/v1/subscription-settings",
        json={"reminder_time": "00:00"},
        headers=headers,
    )

    # Get a pending reminder to obtain a log_id
    resp_pending = await client.post(
        "/api/v1/subscriptions/reminders/pending",
        headers={"X-API-Key": api_key},
    )
    assert resp_pending.status_code == 200
    items = resp_pending.json().get("items", [])
    if not items:
        pytest.skip("No pending reminders to test mark-sent")

    log_id = items[0]["id"]

    # Mark as sent
    resp_sent = await client.post(
        f"/api/v1/subscriptions/reminders/{log_id}/mark-sent",
        headers={"X-API-Key": api_key},
    )
    assert resp_sent.status_code == 200
    sent_data = resp_sent.json()
    assert sent_data["status"] == "sent"
    assert sent_data["sent_at"] is not None


@pytest.mark.asyncio
async def test_subscription_reminder_mark_failed(
    client, db_session, active_tenant_user
):
    """Mark-failed increments attempt_count and retries up to 3."""
    from datetime import datetime, timezone, timedelta

    api_key = settings.n8n_api_key
    tenant = await _tenant_for_user(db_session, active_tenant_user)
    sub_client, service, plan = await _create_subscription_dependencies(
        db_session, tenant, "markfail"
    )

    now = datetime.now(timezone.utc)
    headers = await _login_headers(client, "tenant", "tenant-password")
    resp = await client.post(
        "/api/v1/subscriptions",
        json=_subscription_payload(
            sub_client,
            service,
            plan,
            streaming_password="pwd",
            profile_pin=None,
            profile_name=None,
            duration_type="custom",
            starts_at=now.isoformat(),
            expires_at=(now + timedelta(days=7)).isoformat(),
        ),
        headers=headers,
    )
    assert resp.status_code == 201

    # Set reminder_time to 00:00 so pending endpoint returns reminders
    await client.put(
        "/api/v1/subscription-settings",
        json={"reminder_time": "00:00"},
        headers=headers,
    )

    resp_pending = await client.post(
        "/api/v1/subscriptions/reminders/pending",
        headers={"X-API-Key": api_key},
    )
    assert resp_pending.status_code == 200
    items = resp_pending.json().get("items", [])
    if not items:
        pytest.skip("No pending reminders to test mark-failed")

    log_id = items[0]["id"]

    # Mark failed twice
    for attempt in range(2):
        resp_fail = await client.post(
            f"/api/v1/subscriptions/reminders/{log_id}/mark-failed",
            json={"reason": f"Evolution error attempt {attempt + 1}"},
            headers={"X-API-Key": api_key},
        )
        assert resp_fail.status_code == 200
        fail_data = resp_fail.json()
        assert fail_data["status"] == "pending"  # not yet failed
        assert fail_data["attempt_count"] == attempt + 1
        assert "Evolution error" in (fail_data.get("last_error") or "")

    # Third failure should set status to failed
    resp_fail3 = await client.post(
        f"/api/v1/subscriptions/reminders/{log_id}/mark-failed",
        json={"reason": "Evolution error attempt 3"},
        headers={"X-API-Key": api_key},
    )
    assert resp_fail3.status_code == 200
    fail_data3 = resp_fail3.json()
    assert fail_data3["status"] == "failed"
    assert fail_data3["attempt_count"] == 3


@pytest.mark.asyncio
async def test_subscription_reminder_endpoint_requires_api_key(client):
    """Reminder endpoints return 401 without valid API key."""
    resp = await client.post("/api/v1/subscriptions/reminders/pending")
    assert resp.status_code == 401

    resp = await client.post(
        "/api/v1/subscriptions/reminders/00000000-0000-0000-0000-000000000000/mark-sent",
    )
    assert resp.status_code == 401

    resp = await client.post(
        "/api/v1/subscriptions/reminders/00000000-0000-0000-0000-000000000000/mark-failed",
        json={"reason": "test"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_subscription_reminder_mark_not_found_uses_english_default(
    client, monkeypatch
):
    """404 path uses 'en' locale, no NameError."""
    api_key = settings.n8n_api_key

    async def _none(*args, **kwargs):
        return None

    monkeypatch.setattr(
        "app.services.subscription_job_service.SubscriptionJobService.mark_reminder_sent",
        _none,
    )
    monkeypatch.setattr(
        "app.services.subscription_job_service.SubscriptionJobService.mark_reminder_failed",
        _none,
    )

    for path in (
        "/api/v1/subscriptions/reminders/00000000-0000-0000-0000-000000000000/mark-sent",
        "/api/v1/subscriptions/reminders/00000000-0000-0000-0000-000000000000/mark-failed",
    ):
        kw = {"headers": {"X-API-Key": api_key}}
        if "mark-failed" in path:
            kw["json"] = {"reason": "test"}
        resp = await client.post(path, **kw)
        assert resp.status_code == 404
        assert "Reminder log not found" in resp.json()["detail"]


# ===================================================================
# UserFacingError translation tests for renew/reactivate
# ===================================================================


@pytest.mark.asyncio
async def test_subscription_renew_userfacing_error_translated(
    client, monkeypatch, active_tenant_user
):
    """renew endpoint returns translated message, not raw error code."""
    async def _raise_userfacing(*args, **kwargs):
        raise UserFacingError("subscription_renew_failed")

    monkeypatch.setattr(
        "app.api.v1.endpoints.subscriptions.lifecycle.subscription_service.renew_subscription",
        _raise_userfacing,
    )

    headers = await _login_headers(client, "tenant", "tenant-password")
    sub_id = "00000000-0000-0000-0000-000000000000"
    payload = {"duration_type": "1_month"}

    response = await client.post(
        f"/api/v1/subscriptions/{sub_id}/renew",
        json=payload,
        headers=headers,
    )

    assert response.status_code == 409
    detail = response.json()["detail"]
    assert "subscription_renew_failed" not in detail
    assert detail == "Failed to renew subscription"


@pytest.mark.asyncio
async def test_subscription_reactivate_userfacing_error_translated(
    client, monkeypatch, active_tenant_user
):
    """reactivate endpoint returns translated message, not raw error code."""
    async def _raise_userfacing(*args, **kwargs):
        raise UserFacingError("subscription_reactivate_failed")

    monkeypatch.setattr(
        "app.api.v1.endpoints.subscriptions.lifecycle.subscription_service.reactivate_subscription",
        _raise_userfacing,
    )

    headers = await _login_headers(client, "tenant", "tenant-password")
    sub_id = "00000000-0000-0000-0000-000000000000"
    payload = {"duration_type": "1_month"}

    response = await client.post(
        f"/api/v1/subscriptions/{sub_id}/reactivate",
        json=payload,
        headers=headers,
    )

    assert response.status_code == 409
    detail = response.json()["detail"]
    assert "subscription_reactivate_failed" not in detail
    assert detail == "Failed to reactivate subscription"
