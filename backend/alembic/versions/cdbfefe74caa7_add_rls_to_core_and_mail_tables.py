"""Add RLS to core auth/profile tables and mailbox job tables.

Revision ID: cdbfefe74caa7
Revises: cdbfefe74caa6
"""

from collections.abc import Sequence

from alembic import op  # type: ignore[attr-defined]

revision: str = "cdbfefe74caa7"
down_revision: str | None = "cdbfefe74caa6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Enable RLS
    op.execute("ALTER TABLE users ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE refresh_sessions ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE master_profiles ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE mail_lookup_jobs ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE mail_code_delivery_log ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE alembic_version ENABLE ROW LEVEL SECURITY")

    # Force RLS where runtime access must respect policies
    op.execute("ALTER TABLE users FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE refresh_sessions FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE master_profiles FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE mail_lookup_jobs FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE mail_code_delivery_log FORCE ROW LEVEL SECURITY")

    # Global tables: internal backend/master only
    op.execute(
        """
        CREATE POLICY users_role_or_self ON users
        FOR ALL
        USING (
            current_setting('app.current_role', true) = 'master'
            OR id::text = NULLIF(current_setting('app.current_user_id', true), '')
        )
        WITH CHECK (
            current_setting('app.current_role', true) = 'master'
            OR id::text = NULLIF(current_setting('app.current_user_id', true), '')
        )
        """
    )
    op.execute(
        """
        CREATE POLICY refresh_sessions_role_or_self ON refresh_sessions
        FOR ALL
        USING (
            current_setting('app.current_role', true) = 'master'
            OR user_id::text = NULLIF(current_setting('app.current_user_id', true), '')
        )
        WITH CHECK (
            current_setting('app.current_role', true) = 'master'
            OR user_id::text = NULLIF(current_setting('app.current_user_id', true), '')
        )
        """
    )
    op.execute(
        """
        CREATE POLICY master_profiles_master_only ON master_profiles
        FOR ALL
        USING (current_setting('app.current_role', true) = 'master')
        WITH CHECK (current_setting('app.current_role', true) = 'master')
        """
    )

    # Tenant scoped tables: master(active tenant) + tenant(owner)
    op.execute(
        """
        CREATE POLICY mail_lookup_jobs_tenant_isolation ON mail_lookup_jobs
        FOR ALL
        USING (
            (
                current_setting('app.current_role', true) = 'master'
                AND tenant_id::text = NULLIF(current_setting('app.active_tenant_id', true), '')
            )
            OR (
                current_setting('app.current_role', true) = 'tenant'
                AND EXISTS (
                    SELECT 1 FROM tenants t
                    WHERE t.id = mail_lookup_jobs.tenant_id
                      AND t.owner_user_id::text = NULLIF(current_setting('app.current_user_id', true), '')
                      AND t.is_active
                )
            )
        )
        WITH CHECK (
            (
                current_setting('app.current_role', true) = 'master'
                AND tenant_id::text = NULLIF(current_setting('app.active_tenant_id', true), '')
            )
            OR (
                current_setting('app.current_role', true) = 'tenant'
                AND EXISTS (
                    SELECT 1 FROM tenants t
                    WHERE t.id = mail_lookup_jobs.tenant_id
                      AND t.owner_user_id::text = NULLIF(current_setting('app.current_user_id', true), '')
                      AND t.is_active
                )
            )
        )
        """
    )
    op.execute(
        """
        CREATE POLICY mail_code_delivery_log_tenant_isolation ON mail_code_delivery_log
        FOR ALL
        USING (
            (
                current_setting('app.current_role', true) = 'master'
                AND tenant_id::text = NULLIF(current_setting('app.active_tenant_id', true), '')
            )
            OR (
                current_setting('app.current_role', true) = 'tenant'
                AND EXISTS (
                    SELECT 1 FROM tenants t
                    WHERE t.id = mail_code_delivery_log.tenant_id
                      AND t.owner_user_id::text = NULLIF(current_setting('app.current_user_id', true), '')
                      AND t.is_active
                )
            )
        )
        WITH CHECK (
            (
                current_setting('app.current_role', true) = 'master'
                AND tenant_id::text = NULLIF(current_setting('app.active_tenant_id', true), '')
            )
            OR (
                current_setting('app.current_role', true) = 'tenant'
                AND EXISTS (
                    SELECT 1 FROM tenants t
                    WHERE t.id = mail_code_delivery_log.tenant_id
                      AND t.owner_user_id::text = NULLIF(current_setting('app.current_user_id', true), '')
                      AND t.is_active
                )
            )
        )
        """
    )

    # Keep alembic migrations operable: do not FORCE this table.
    op.execute(
        """
        CREATE POLICY alembic_version_master_only ON alembic_version
        FOR ALL
        USING (current_setting('app.current_role', true) = 'master')
        WITH CHECK (current_setting('app.current_role', true) = 'master')
        """
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS alembic_version_master_only ON alembic_version")
    op.execute(
        "DROP POLICY IF EXISTS mail_code_delivery_log_tenant_isolation ON mail_code_delivery_log"
    )
    op.execute(
        "DROP POLICY IF EXISTS mail_lookup_jobs_tenant_isolation ON mail_lookup_jobs"
    )
    op.execute("DROP POLICY IF EXISTS master_profiles_master_only ON master_profiles")
    op.execute(
        "DROP POLICY IF EXISTS refresh_sessions_role_or_self ON refresh_sessions"
    )
    op.execute("DROP POLICY IF EXISTS users_role_or_self ON users")

    op.execute("ALTER TABLE mail_code_delivery_log NO FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE mail_lookup_jobs NO FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE master_profiles NO FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE refresh_sessions NO FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE users NO FORCE ROW LEVEL SECURITY")

    op.execute("ALTER TABLE alembic_version DISABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE mail_code_delivery_log DISABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE mail_lookup_jobs DISABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE master_profiles DISABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE refresh_sessions DISABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE users DISABLE ROW LEVEL SECURITY")
