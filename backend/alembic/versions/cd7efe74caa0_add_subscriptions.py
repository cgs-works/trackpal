"""add subscriptions

Revision ID: cd7efe74caa0
Revises: cd6efe74cae9
Create Date: 2026-05-20 21:30:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "cd7efe74caa0"
down_revision: Union[str, Sequence[str], None] = "cd6efe74cae9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_TABLES = (
    "subscriptions",
    "subscription_events",
    "subscription_reminder_logs",
    "subscription_reminder_settings",
)

_POLICY_NAMES = (
    "CREATE POLICY subscriptions_tenant_isolation",
    "CREATE POLICY subscription_events_tenant_isolation",
    "CREATE POLICY subscription_reminder_logs_tenant_isolation",
    "CREATE POLICY subscription_reminder_settings_tenant_isolation",
)

_ENABLE_RLS_STATEMENTS = (
    "ALTER TABLE subscriptions ENABLE ROW LEVEL SECURITY",
    "ALTER TABLE subscription_events ENABLE ROW LEVEL SECURITY",
    "ALTER TABLE subscription_reminder_logs ENABLE ROW LEVEL SECURITY",
    "ALTER TABLE subscription_reminder_settings ENABLE ROW LEVEL SECURITY",
)

_FORCE_RLS_STATEMENTS = (
    "ALTER TABLE subscriptions FORCE ROW LEVEL SECURITY",
    "ALTER TABLE subscription_events FORCE ROW LEVEL SECURITY",
    "ALTER TABLE subscription_reminder_logs FORCE ROW LEVEL SECURITY",
    "ALTER TABLE subscription_reminder_settings FORCE ROW LEVEL SECURITY",
)

_POLICY_TENANT_CHECKS = (
    "t.id = subscriptions.tenant_id",
    "t.id = subscription_events.tenant_id",
    "t.id = subscription_reminder_logs.tenant_id",
    "t.id = subscription_reminder_settings.tenant_id",
)


def _tenant_policy(table_name: str) -> str:
    return f"""
        CREATE POLICY {table_name}_tenant_isolation ON {table_name}
        USING (
            (
                current_setting('app.current_role', true) = 'master'
                AND tenant_id::text = NULLIF(current_setting('app.active_tenant_id', true), '')
            )
            OR (
                current_setting('app.current_role', true) = 'tenant'
                AND EXISTS (
                    SELECT 1
                    FROM tenants t
                    WHERE t.id = {table_name}.tenant_id
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
                    SELECT 1
                    FROM tenants t
                    WHERE t.id = {table_name}.tenant_id
                      AND t.owner_user_id::text = NULLIF(current_setting('app.current_user_id', true), '')
                      AND t.is_active
                )
            )
        )
    """


def upgrade() -> None:
    op.create_table(
        "subscriptions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("client_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("service_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("plan_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("streaming_email", sa.String(length=255), nullable=False),
        sa.Column("streaming_password_encrypted", sa.String(length=500), nullable=True),
        sa.Column("profile_name", sa.String(length=100), nullable=True),
        sa.Column("profile_pin_encrypted", sa.String(length=500), nullable=True),
        sa.Column("duration_type", sa.String(length=50), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "status", sa.String(length=50), server_default="active", nullable=False
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
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["client_id"], ["clients.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["tenant_id", "service_id"],
            ["services.tenant_id", "services.id"],
            ondelete="CASCADE",
            name="fk_subscriptions_tenant_service",
        ),
        sa.ForeignKeyConstraint(["plan_id"], ["plans.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_subscriptions_tenant_status", "subscriptions", ["tenant_id", "status"]
    )
    op.create_index(
        "ix_subscriptions_tenant_client", "subscriptions", ["tenant_id", "client_id"]
    )
    op.create_index(
        "ix_subscriptions_tenant_service", "subscriptions", ["tenant_id", "service_id"]
    )
    op.create_index(
        "ix_subscriptions_tenant_expires_at",
        "subscriptions",
        ["tenant_id", "expires_at"],
    )

    op.create_table(
        "subscription_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("subscription_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_type", sa.String(length=100), nullable=False),
        sa.Column("notes", sa.String(length=1000), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
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
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["subscription_id"], ["subscriptions.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_subscription_events_tenant_subscription",
        "subscription_events",
        ["tenant_id", "subscription_id"],
    )

    op.create_table(
        "subscription_reminder_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("subscription_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("recipient_type", sa.String(length=50), nullable=False),
        sa.Column("recipient_phone", sa.String(length=50), nullable=True),
        sa.Column("days_before_expiry", sa.Integer(), nullable=False),
        sa.Column("sent_for_date", sa.Date(), nullable=False),
        sa.Column(
            "status", sa.String(length=50), server_default="pending", nullable=False
        ),
        sa.Column("attempt_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("last_error", sa.String(length=1000), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["subscription_id"], ["subscriptions.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "subscription_id",
            "recipient_type",
            "days_before_expiry",
            "sent_for_date",
            name="uq_subscription_reminder_dedupe",
        ),
    )
    op.create_index(
        "ix_subscription_reminder_logs_tenant_status",
        "subscription_reminder_logs",
        ["tenant_id", "status"],
    )

    op.create_table(
        "subscription_reminder_settings",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "timezone", sa.String(length=100), server_default="UTC", nullable=False
        ),
        sa.Column(
            "warning_days",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[7, 3, 1]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "reminder_time", sa.String(length=5), server_default="09:00", nullable=False
        ),
        sa.Column(
            "recipient_mode",
            sa.String(length=50),
            server_default="tenant_only",
            nullable=False,
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
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id", name="uq_subscription_reminder_settings_tenant_id"
        ),
    )

    for statement in _ENABLE_RLS_STATEMENTS:
        op.execute(statement)
    for statement in _FORCE_RLS_STATEMENTS:
        op.execute(statement)
    for table in _TABLES:
        op.execute(_tenant_policy(table))


def downgrade() -> None:
    for table in reversed(_TABLES):
        op.execute(f"DROP POLICY IF EXISTS {table}_tenant_isolation ON {table}")
        op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")

    op.drop_table("subscription_reminder_settings")
    op.drop_index(
        "ix_subscription_reminder_logs_tenant_status",
        table_name="subscription_reminder_logs",
    )
    op.drop_table("subscription_reminder_logs")
    op.drop_index(
        "ix_subscription_events_tenant_subscription", table_name="subscription_events"
    )
    op.drop_table("subscription_events")
    op.drop_index("ix_subscriptions_tenant_expires_at", table_name="subscriptions")
    op.drop_index("ix_subscriptions_tenant_service", table_name="subscriptions")
    op.drop_index("ix_subscriptions_tenant_client", table_name="subscriptions")
    op.drop_index("ix_subscriptions_tenant_status", table_name="subscriptions")
    op.drop_table("subscriptions")
