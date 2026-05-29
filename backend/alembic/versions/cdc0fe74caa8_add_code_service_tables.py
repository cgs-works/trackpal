"""Add code_service_global_status, tenant_code_service_selections + RLS.

Revision ID: cdc0fe74caa8
Revises: cdbfefe74caa7
Create Date: 2026-05-28 12:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "cdc0fe74caa8"
down_revision: str | None = "cdbfefe74caa7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# ── Pre-defined globally supported code service keys ────────────────────
# Alphabetical by visible label: Disney+, HBO Max, Netflix, Prime Video,
# Spotify, Universal+
_SEED_ROWS = [
    ("disney", True),
    ("hbo_max", True),
    ("netflix", True),
    ("prime_video", True),
    ("spotify", True),
    ("universal_plus", True),
]


def upgrade() -> None:
    # ── 1. Global status table (master-controlled) ──────────────────────
    op.create_table(
        "code_service_global_status",
        sa.Column("service_key", sa.String(50), primary_key=True),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )

    # Seed global rows — all active by default
    bind = op.get_bind()
    for key, active in _SEED_ROWS:
        bind.execute(
            sa.text(
                "INSERT INTO code_service_global_status (service_key, is_active) "
                "VALUES (:key, :active)"
            ),
            {"key": key, "active": active},
        )

    # ── 2. Tenant selection table ───────────────────────────────────────
    op.create_table(
        "tenant_code_service_selections",
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("service_key", sa.String(50), primary_key=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )

    # ── 3. RLS policies ────────────────────────────────────────────────
    # Global status: master-only
    op.execute("ALTER TABLE code_service_global_status ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE code_service_global_status FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY code_service_global_master_only ON code_service_global_status
        FOR ALL
        USING (current_setting('app.current_role', true) = 'master')
        WITH CHECK (current_setting('app.current_role', true) = 'master')
        """
    )

    # Tenant selection: tenant isolation (same pattern as mail_lookup_jobs)
    op.execute("ALTER TABLE tenant_code_service_selections ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE tenant_code_service_selections FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_code_selections_isolation ON tenant_code_service_selections
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
                    WHERE t.id = tenant_code_service_selections.tenant_id
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
                    WHERE t.id = tenant_code_service_selections.tenant_id
                      AND t.owner_user_id::text = NULLIF(current_setting('app.current_user_id', true), '')
                      AND t.is_active
                )
            )
        )
        """
    )


def downgrade() -> None:
    op.execute(
        "DROP POLICY IF EXISTS tenant_code_selections_isolation ON tenant_code_service_selections"
    )
    op.execute("ALTER TABLE tenant_code_service_selections NO FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE tenant_code_service_selections DISABLE ROW LEVEL SECURITY")
    op.drop_table("tenant_code_service_selections")

    op.execute(
        "DROP POLICY IF EXISTS code_service_global_master_only ON code_service_global_status"
    )
    op.execute("ALTER TABLE code_service_global_status NO FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE code_service_global_status DISABLE ROW LEVEL SECURITY")
    op.drop_table("code_service_global_status")
