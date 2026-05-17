from pathlib import Path

import pytest


def test_rls_policy_sql_uses_required_context_settings():
    text = Path("alembic/versions/cd3efe74cae6_tenant_catalog_rls.py").read_text()
    text += Path("alembic/versions/cd4efe74cae7_fix_tenants_master_rls.py").read_text()
    assert "ENABLE ROW LEVEL SECURITY" in text
    assert "FORCE ROW LEVEL SECURITY" in text
    assert "WITH CHECK" in text
    assert "app.current_user_id" in text
    assert "app.current_role" in text
    assert "app.active_tenant_id" in text
    assert "services_tenant_isolation" in text
    assert "plans_tenant_isolation" in text
    assert "tenants_tenant_isolation" in text
    assert "current_setting('app.current_role', true) = 'master'" in text


def test_tenants_policy_allows_master_management_without_active_tenant_context():
    text = Path("alembic/versions/cd4efe74cae7_fix_tenants_master_rls.py").read_text()
    using_block = text.split("USING (", 1)[1].split(")\n        WITH CHECK", 1)[0]
    assert "current_setting('app.current_role', true) = 'master'" in using_block
    assert "app.active_tenant_id" not in using_block


@pytest.mark.skip(reason="Requires disposable Postgres/app-role DATABASE_URL and is run manually before production deploy")
def test_postgres_rls_behavior_manual_gate_documented():
    """Placeholder gate for manual Postgres RLS QA.

    The implementation plan and execution report require a disposable Supabase/Postgres
    app-role check for actual RLS behavior because SQLite cannot enforce policies.
    Keep this skipped marker visible so the security gate is not confused with normal
    unit coverage.
    """
    assert True
