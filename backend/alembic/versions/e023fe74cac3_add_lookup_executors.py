"""Persist external lookup executors and assignment metadata.

Revision ID: e023fe74cac3
Revises: e022fe74cac2
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e023fe74cac3"
down_revision: str | None = "e022fe74cac2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "lookup_executors",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("provider_label", sa.String(length=50), nullable=False),
        sa.Column("base_url", sa.String(length=500), nullable=False),
        sa.Column(
            "transport_mode",
            sa.String(length=30),
            server_default="https",
            nullable=False,
        ),
        sa.Column(
            "lifecycle_status",
            sa.String(length=20),
            server_default="draft",
            nullable=False,
        ),
        sa.Column(
            "health_status",
            sa.String(length=20),
            server_default="unknown",
            nullable=False,
        ),
        sa.Column(
            "requires_reverification",
            sa.Boolean(),
            server_default=sa.false(),
            nullable=False,
        ),
        sa.Column("max_concurrency", sa.Integer(), server_default="1", nullable=False),
        sa.Column("secret_encrypted", sa.String(length=500), nullable=False),
        sa.Column("secret_version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("pending_secret_encrypted", sa.String(length=500), nullable=True),
        sa.Column("pending_secret_version", sa.Integer(), nullable=True),
        sa.Column("hosting_account_email", sa.String(length=255), nullable=True),
        sa.Column("hosting_account_password_encrypted", sa.Text(), nullable=True),
        sa.Column("dashboard_url", sa.String(length=500), nullable=True),
        sa.Column("last_health_check_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_success_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error_safe", sa.String(length=1000), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_lookup_executors_lifecycle_status",
        "lookup_executors",
        ["lifecycle_status"],
    )
    op.create_index(
        "ix_lookup_executors_health_status", "lookup_executors", ["health_status"]
    )

    op.add_column(
        "mail_lookup_jobs",
        sa.Column("executor_id", sa.Uuid(), nullable=True),
    )
    op.create_index(
        "ix_mail_lookup_jobs_executor_id", "mail_lookup_jobs", ["executor_id"]
    )
    op.create_foreign_key(
        "fk_mail_lookup_jobs_executor_id",
        "mail_lookup_jobs",
        "lookup_executors",
        ["executor_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.add_column(
        "mail_lookup_jobs",
        sa.Column(
            "execution_attempts", sa.Integer(), server_default="0", nullable=False
        ),
    )
    op.add_column(
        "mail_lookup_jobs",
        sa.Column("last_dispatch_error_safe", sa.String(length=1000), nullable=True),
    )
    op.drop_column("mail_lookup_jobs", "result_value_encrypted")

    op.execute("ALTER TABLE lookup_executors ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE lookup_executors FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY lookup_executors_master_only ON lookup_executors
        FOR ALL
        USING (current_setting('app.current_role', true) = 'master')
        WITH CHECK (current_setting('app.current_role', true) = 'master')
        """
    )


def downgrade() -> None:
    op.add_column(
        "mail_lookup_jobs",
        sa.Column("result_value_encrypted", sa.String(length=2000), nullable=True),
    )
    op.drop_column("mail_lookup_jobs", "last_dispatch_error_safe")
    op.drop_column("mail_lookup_jobs", "execution_attempts")
    op.drop_constraint(
        "fk_mail_lookup_jobs_executor_id", "mail_lookup_jobs", type_="foreignkey"
    )
    op.drop_index("ix_mail_lookup_jobs_executor_id", table_name="mail_lookup_jobs")
    op.drop_column("mail_lookup_jobs", "executor_id")

    op.execute("DROP POLICY IF EXISTS lookup_executors_master_only ON lookup_executors")
    op.execute("ALTER TABLE lookup_executors NO FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE lookup_executors DISABLE ROW LEVEL SECURITY")
    op.drop_index("ix_lookup_executors_health_status", table_name="lookup_executors")
    op.drop_index("ix_lookup_executors_lifecycle_status", table_name="lookup_executors")
    op.drop_table("lookup_executors")
