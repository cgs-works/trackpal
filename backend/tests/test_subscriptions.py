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
    res = await db_session.execute(select(Tenant).where(Tenant.owner_user_id == active_tenant_user.id))
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
        local_username="subclient1",
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
    res = await db_session.execute(select(Tenant).where(Tenant.owner_user_id == active_tenant_user.id))
    tenant = res.scalar_one()

    # Minimal Subscription setup
    client_user = User(username="evt_client", password_hash="hash", role="client")
    db_session.add(client_user)
    await db_session.flush()
    client = Client(tenant_id=tenant.id, owner_user_id=client_user.id, full_name="Evt Client", local_username="evtclient", is_active=True)
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
    res = await db_session.execute(select(Tenant).where(Tenant.owner_user_id == active_tenant_user.id))
    tenant = res.scalar_one()

    # Minimal setup
    client_user = User(username="rem_client", password_hash="hash", role="client")
    db_session.add(client_user)
    await db_session.flush()
    client = Client(tenant_id=tenant.id, owner_user_id=client_user.id, full_name="Rem Client", local_username="remclient", is_active=True)
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
    res = await db_session.execute(select(Tenant).where(Tenant.owner_user_id == active_tenant_user.id))
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
