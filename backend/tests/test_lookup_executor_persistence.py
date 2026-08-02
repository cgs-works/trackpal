"""Persistence contracts for the external lookup executor registry."""

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from sqlalchemy import Text

from app.models import LookupExecutor, MailLookupJob, Tenant, TenantMailbox, User
from app.repositories import lookup_executors_repository, mailbox_lookup_repository
from app.schemas.lookup_executors import LookupExecutorResponse


async def _tenant_and_mailbox(db_session):
    user = User(
        username=f"executor-test-{uuid4().hex[:8]}",
        password_hash="not-used",
        role="tenant",
    )
    db_session.add(user)
    await db_session.flush()
    tenant = Tenant(
        owner_user_id=user.id,
        client_prefix=f"ext{uuid4().hex[:4]}",
        name="Executor Test Tenant",
        is_active=True,
    )
    db_session.add(tenant)
    await db_session.flush()
    mailbox = TenantMailbox(
        tenant_id=tenant.id,
        mailbox_email="codes@example.com",
        status="connected",
    )
    db_session.add(mailbox)
    await db_session.commit()
    return tenant, mailbox


@pytest.mark.asyncio
async def test_create_encrypts_protocol_and_hosting_passwords(db_session):
    executor = await lookup_executors_repository.create(
        db_session,
        name="Executor One",
        provider_label="render",
        base_url="https://executor.example.com",
        secret="protocol-secret",
        hosting_account_email="hosting@example.com",
        hosting_account_password="hosting-password",
    )

    assert executor.secret_encrypted != "protocol-secret"
    assert executor.hosting_account_password_encrypted != "hosting-password"
    assert executor.secret_encrypted
    assert executor.hosting_account_password_encrypted


@pytest.mark.asyncio
async def test_hosting_password_column_supports_500_character_plaintext(db_session):
    password = "p" * 500
    executor = await lookup_executors_repository.create(
        db_session,
        name="Long Password Executor",
        provider_label="custom",
        base_url="https://executor.example.com",
        secret="protocol-secret",
        hosting_account_password=password,
    )
    await db_session.commit()

    assert len(executor.hosting_account_password_encrypted) > 500
    column = LookupExecutor.__table__.c.hosting_account_password_encrypted
    assert isinstance(column.type, Text)


@pytest.mark.asyncio
async def test_response_serialization_exposes_only_hosting_password_presence(
    db_session,
):
    executor = await lookup_executors_repository.create(
        db_session,
        name="Safe Executor",
        provider_label="custom",
        base_url="https://executor.example.com",
        secret="protocol-secret",
        hosting_account_password="hosting-password",
    )
    await db_session.commit()
    await db_session.refresh(executor)

    response = LookupExecutorResponse.model_validate(executor)
    serialized = response.model_dump()

    assert serialized["has_hosting_password"] is True
    assert "secret_encrypted" not in serialized
    assert "hosting_account_password_encrypted" not in serialized
    assert "hosting_password" not in serialized


@pytest.mark.asyncio
async def test_list_and_get_include_active_job_count(db_session):
    tenant, mailbox = await _tenant_and_mailbox(db_session)
    executor = await lookup_executors_repository.create(
        db_session,
        name="Busy Executor",
        provider_label="custom",
        base_url="https://executor.example.com",
        secret="protocol-secret",
    )
    db_session.add(
        MailLookupJob(
            tenant_id=tenant.id,
            mailbox_id=mailbox.id,
            executor_id=executor.id,
            service_key="netflix",
            target_email="active@example.com",
            status="pending",
        )
    )
    db_session.add(
        MailLookupJob(
            tenant_id=tenant.id,
            mailbox_id=mailbox.id,
            executor_id=executor.id,
            service_key="disney",
            target_email="processing@example.com",
            status="processing",
        )
    )
    db_session.add(
        MailLookupJob(
            tenant_id=tenant.id,
            mailbox_id=mailbox.id,
            executor_id=executor.id,
            service_key="hbo",
            target_email="completed@example.com",
            status="completed",
        )
    )
    await db_session.commit()

    listed = await lookup_executors_repository.list_all(db_session)
    fetched = await lookup_executors_repository.get(db_session, executor.id)

    assert listed[0].active_jobs == 2
    assert fetched is not None
    assert fetched.active_jobs == 2


@pytest.mark.asyncio
async def test_list_dispatchable_excludes_disabled_and_reverification_rows(db_session):
    active = await lookup_executors_repository.create(
        db_session,
        name="Active",
        provider_label="custom",
        base_url="https://active.example.com",
        secret="secret-a",
        lifecycle_status="active",
    )
    disabled = await lookup_executors_repository.create(
        db_session,
        name="Disabled",
        provider_label="custom",
        base_url="https://disabled.example.com",
        secret="secret-b",
        lifecycle_status="disabled",
    )
    quarantined = await lookup_executors_repository.create(
        db_session,
        name="Quarantined",
        provider_label="custom",
        base_url="https://quarantined.example.com",
        secret="secret-c",
        lifecycle_status="active",
        requires_reverification=True,
    )
    await db_session.commit()

    dispatchable = await lookup_executors_repository.list_dispatchable(db_session)

    assert [item.id for item in dispatchable] == [active.id]
    assert disabled.id not in {item.id for item in dispatchable}
    assert quarantined.id not in {item.id for item in dispatchable}


@pytest.mark.asyncio
async def test_processing_job_can_recover_to_pending_and_clear_assignment_fields(
    db_session,
):
    tenant, mailbox = await _tenant_and_mailbox(db_session)
    executor = await lookup_executors_repository.create(
        db_session,
        name="Assigned",
        provider_label="custom",
        base_url="https://executor.example.com",
        secret="secret",
    )
    await db_session.flush()
    job = MailLookupJob(
        tenant_id=tenant.id,
        mailbox_id=mailbox.id,
        service_key="netflix",
        target_email="client@example.com",
        status="processing",
        executor_id=executor.id,
        execution_attempts=1,
        processing_started_at=datetime.now(timezone.utc),
        completed_at=datetime.now(timezone.utc),
    )
    db_session.add(job)
    await db_session.flush()

    await mailbox_lookup_repository.transition_status(
        db_session, job, "pending", error_detail_safe="Executor lease expired"
    )

    assert job.status == "pending"
    assert job.executor_id is None
    assert job.processing_started_at is None
    assert job.completed_at is None
    assert job.last_dispatch_error_safe == "Executor lease expired"


def test_removed_result_value_column_is_rejected():
    with pytest.raises(TypeError):
        MailLookupJob(
            tenant_id=uuid4(),
            mailbox_id=uuid4(),
            service_key="netflix",
            target_email="client@example.com",
            result_value_encrypted="must-not-be-persisted",
        )
