from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.core.database import (
    SYSTEM_RLS_USER_ID,
    get_rls_context,
    restore_rls_context,
    set_internal_rls_context,
    set_rls_context,
)


def test_rls_policy_sql_uses_required_context_settings():
    text = Path("alembic/versions/cd3efe74cae6_tenant_catalog_rls.py").read_text()
    text += Path("alembic/versions/cd4efe74cae7_fix_tenants_master_rls.py").read_text()
    text += Path("alembic/versions/cd6efe74cae9_add_client_prefix_and_clients.py").read_text()
    text += Path("alembic/versions/cd7efe74caa0_add_subscriptions.py").read_text()
    assert "ENABLE ROW LEVEL SECURITY" in text
    assert "FORCE ROW LEVEL SECURITY" in text
    assert "WITH CHECK" in text
    assert "app.current_user_id" in text
    assert "app.current_role" in text
    assert "app.active_tenant_id" in text
    assert "services_tenant_isolation" in text
    assert "plans_tenant_isolation" in text
    assert "tenants_tenant_isolation" in text
    assert "clients_tenant_isolation" in text
    assert "subscriptions_tenant_isolation" in text
    assert "subscription_events_tenant_isolation" in text
    assert "subscription_reminder_logs_tenant_isolation" in text
    assert "subscription_reminder_settings_tenant_isolation" in text
    assert "current_setting('app.current_role', true) = 'master'" in text


def test_tenants_policy_allows_master_management_without_active_tenant_context():
    text = Path("alembic/versions/cd4efe74cae7_fix_tenants_master_rls.py").read_text()
    using_block = text.split("USING (", 1)[1].split(")\n        WITH CHECK", 1)[0]
    assert "current_setting('app.current_role', true) = 'master'" in using_block
    assert "app.active_tenant_id" not in using_block


def test_tenants_policy_allows_tenant_to_read_inactive_own_row_for_app_check():
    text = Path("alembic/versions/cd4efe74cae7_fix_tenants_master_rls.py").read_text()
    using_block = text.split("USING (", 1)[1].split(")\n        WITH CHECK", 1)[0]
    tenant_branch = using_block.split("current_setting('app.current_role', true) = 'tenant'", 1)[1]

    assert "owner_user_id::text = NULLIF(current_setting('app.current_user_id', true), '')" in tenant_branch
    assert "AND is_active" not in tenant_branch


def test_service_and_plan_policies_keep_active_tenant_requirement():
    text = Path("alembic/versions/cd3efe74cae6_tenant_catalog_rls.py").read_text()

    assert "t.id = services.tenant_id" in text
    assert "t.id = plans.tenant_id" in text
    assert "AND t.is_active" in text


def test_service_and_plan_with_check_validate_tenant_ownership_for_writes():
    text = Path("alembic/versions/cd3efe74cae6_tenant_catalog_rls.py").read_text()
    services_policy = text.split("CREATE POLICY services_tenant_isolation", 1)[1].split("CREATE POLICY plans_tenant_isolation", 1)[0]
    plans_policy = text.split("CREATE POLICY plans_tenant_isolation", 1)[1].split("def downgrade", 1)[0]

    assert "WITH CHECK (" in services_policy
    assert "current_setting('app.current_role', true) = 'master'" in services_policy
    assert "tenant_id::text = NULLIF(current_setting('app.active_tenant_id', true), '')" in services_policy
    assert "t.id = services.tenant_id" in services_policy
    assert "t.owner_user_id::text = NULLIF(current_setting('app.current_user_id', true), '')" in services_policy
    assert "AND t.is_active" in services_policy

    assert "WITH CHECK (" in plans_policy
    assert "current_setting('app.current_role', true) = 'master'" in plans_policy
    assert "tenant_id::text = NULLIF(current_setting('app.active_tenant_id', true), '')" in plans_policy
    assert "t.id = plans.tenant_id" in plans_policy
    assert "t.owner_user_id::text = NULLIF(current_setting('app.current_user_id', true), '')" in plans_policy
    assert "AND t.is_active" in plans_policy


def test_clients_policy_enforces_tenant_and_client_context():
    text = Path("alembic/versions/cd6efe74cae9_add_client_prefix_and_clients.py").read_text()
    policy = text.split("CREATE POLICY clients_tenant_isolation", 1)[1].split("def downgrade", 1)[0]

    assert "ALTER TABLE clients ENABLE ROW LEVEL SECURITY" in text
    assert "ALTER TABLE clients FORCE ROW LEVEL SECURITY" in text
    assert "current_setting('app.current_role', true) = 'master'" in policy
    assert "current_setting('app.current_role', true) = 'tenant'" in policy
    assert "current_setting('app.current_role', true) = 'client'" in policy
    assert "owner_user_id::text = NULLIF(current_setting('app.current_user_id', true), '')" in policy
    assert "AND is_active" in policy
    assert "AND false" in policy


def test_subscription_policies_enforce_tenant_context():
    text = Path("alembic/versions/cd7efe74caa0_add_subscriptions.py").read_text()

    for table in (
        "subscriptions",
        "subscription_events",
        "subscription_reminder_logs",
        "subscription_reminder_settings",
    ):
        assert f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY" in text
        assert f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY" in text
        assert f"CREATE POLICY {table}_tenant_isolation" in text

    assert "current_setting('app.current_role', true) = 'master'" in text
    assert "tenant_id::text = NULLIF(current_setting('app.active_tenant_id', true), '')" in text
    assert "current_setting('app.current_role', true) = 'tenant'" in text
    assert "t.id = subscriptions.tenant_id" in text
    assert "t.id = subscription_events.tenant_id" in text
    assert "t.id = subscription_reminder_logs.tenant_id" in text
    assert "t.id = subscription_reminder_settings.tenant_id" in text
    assert "t.owner_user_id::text = NULLIF(current_setting('app.current_user_id', true), '')" in text
    assert "AND t.is_active" in text



@pytest.mark.asyncio
async def test_set_rls_context_stores_context_on_sqlite(db_session):
    await set_rls_context(db_session, "user-1", "tenant", "tenant-1")

    assert get_rls_context(db_session) == {
        "user_id": "user-1",
        "role": "tenant",
        "active_tenant_id": "tenant-1",
    }


@pytest.mark.asyncio
async def test_set_rls_context_stores_client_context_on_sqlite(db_session):
    await set_rls_context(db_session, "user-2", "client", "tenant-2")

    assert get_rls_context(db_session) == {
        "user_id": "user-2",
        "role": "client",
        "active_tenant_id": "tenant-2",
    }


@pytest.mark.asyncio
async def test_set_rls_context_requires_tenant_id_for_postgres():
    session = SimpleNamespace(
        info={},
        get_bind=lambda: SimpleNamespace(dialect=SimpleNamespace(name="postgresql")),
        execute=AsyncMock(),
    )

    with pytest.raises(ValueError, match="active_tenant_id required"):
        await set_rls_context(session, "user-1", "tenant", None)

    session.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_restore_rls_context_reapplies_postgres_transaction_settings():
    session = SimpleNamespace(
        info={},
        get_bind=lambda: SimpleNamespace(dialect=SimpleNamespace(name="postgresql")),
        execute=AsyncMock(),
    )

    await set_rls_context(session, "user-1", "tenant", "tenant-1")
    await restore_rls_context(session)

    assert session.execute.await_count == 2
    second_args, second_kwargs = session.execute.await_args_list[1]
    assert second_kwargs == {}
    assert second_args[1] == {
        "user_id": "user-1",
        "role": "tenant",
        "tenant_id": "tenant-1",
    }


@pytest.mark.asyncio
async def test_internal_rls_context_uses_master_without_active_tenant():
    session = SimpleNamespace(
        info={},
        get_bind=lambda: SimpleNamespace(dialect=SimpleNamespace(name="postgresql")),
        execute=AsyncMock(),
    )

    await set_internal_rls_context(session)

    first_args, first_kwargs = session.execute.await_args
    assert first_kwargs == {}
    assert first_args[1] == {
        "user_id": SYSTEM_RLS_USER_ID,
        "role": "master",
        "tenant_id": "",
    }


@pytest.mark.skip(reason="Requires disposable Postgres/app-role DATABASE_URL and is run manually before production deploy")
def test_postgres_rls_behavior_manual_gate_documented():
    """Placeholder gate for manual Postgres RLS QA.

    The implementation plan and execution report require a disposable Supabase/Postgres
    app-role check for actual RLS behavior because SQLite cannot enforce policies.
    Keep this skipped marker visible so the security gate is not confused with normal
    unit coverage.
    """
    assert True
