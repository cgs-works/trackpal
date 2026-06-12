"""create tenant settings

Revision ID: d011fe74cab0
Revises: 07fa809c3ab3
Create Date: 2026-06-12 17:30:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "d011fe74cab0"
down_revision: Union[str, Sequence[str], None] = "07fa809c3ab3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _tenant_settings_select_policy() -> str:
    return """
        CREATE POLICY tenant_settings_select ON tenant_settings
        FOR SELECT
        USING (
            current_setting('app.current_role', true) = 'master'
            OR (
                current_setting('app.current_role', true) = 'tenant'
                AND EXISTS (
                    SELECT 1
                    FROM tenants t
                    WHERE t.id = tenant_settings.tenant_id
                      AND t.owner_user_id::text = NULLIF(current_setting('app.current_user_id', true), '')
                )
            )
        )
    """


def _tenant_settings_write_condition() -> str:
    return """
            current_setting('app.current_role', true) = 'master'
            OR (
                current_setting('app.current_role', true) = 'tenant'
                AND EXISTS (
                    SELECT 1
                    FROM tenants t
                    WHERE t.id = tenant_settings.tenant_id
                      AND t.owner_user_id::text = NULLIF(current_setting('app.current_user_id', true), '')
                      AND t.is_active
                )
            )
    """


def _tenant_settings_insert_policy() -> str:
    return f"""
        CREATE POLICY tenant_settings_insert ON tenant_settings
        FOR INSERT
        WITH CHECK ({_tenant_settings_write_condition()})
    """


def _tenant_settings_update_policy() -> str:
    condition = _tenant_settings_write_condition()
    return f"""
        CREATE POLICY tenant_settings_update ON tenant_settings
        FOR UPDATE
        USING ({condition})
        WITH CHECK ({condition})
    """


def _tenant_settings_delete_policy() -> str:
    return f"""
        CREATE POLICY tenant_settings_delete ON tenant_settings
        FOR DELETE
        USING ({_tenant_settings_write_condition()})
    """


def upgrade() -> None:
    op.create_table(
        "tenant_settings",
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("locale", sa.String(length=10), server_default="en", nullable=False),
        sa.Column(
            "timezone", sa.String(length=100), server_default="UTC", nullable=False
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
        sa.PrimaryKeyConstraint("tenant_id"),
    )

    op.execute(
        """
        INSERT INTO tenant_settings (tenant_id, locale, timezone)
        SELECT
            t.id,
            COALESCE(t.locale, 'en'),
            COALESCE(srs.timezone, 'UTC')
        FROM tenants t
        LEFT JOIN subscription_reminder_settings srs
            ON srs.tenant_id = t.id
        """
    )

    op.drop_column("subscription_reminder_settings", "timezone")
    op.drop_column("tenants", "locale")

    op.execute("ALTER TABLE tenant_settings ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE tenant_settings FORCE ROW LEVEL SECURITY")
    op.execute(_tenant_settings_select_policy())
    op.execute(_tenant_settings_insert_policy())
    op.execute(_tenant_settings_update_policy())
    op.execute(_tenant_settings_delete_policy())


def downgrade() -> None:
    op.add_column(
        "tenants",
        sa.Column("locale", sa.String(length=10), nullable=True),
    )
    op.execute(
        """
        UPDATE tenants
        SET locale = COALESCE(ts.locale, 'en')
        FROM tenant_settings ts
        WHERE ts.tenant_id = tenants.id
        """
    )
    op.execute("UPDATE tenants SET locale = 'en' WHERE locale IS NULL")
    op.alter_column(
        "tenants",
        "locale",
        existing_type=sa.String(length=10),
        nullable=False,
        server_default="en",
    )

    op.add_column(
        "subscription_reminder_settings",
        sa.Column(
            "timezone",
            sa.String(length=100),
            server_default="UTC",
            nullable=False,
        ),
    )
    op.execute(
        """
        UPDATE subscription_reminder_settings
        SET timezone = COALESCE(ts.timezone, 'UTC')
        FROM tenant_settings ts
        WHERE ts.tenant_id = subscription_reminder_settings.tenant_id
        """
    )

    op.execute("DROP POLICY IF EXISTS tenant_settings_delete ON tenant_settings")
    op.execute("DROP POLICY IF EXISTS tenant_settings_update ON tenant_settings")
    op.execute("DROP POLICY IF EXISTS tenant_settings_insert ON tenant_settings")
    op.execute("DROP POLICY IF EXISTS tenant_settings_select ON tenant_settings")
    op.execute("ALTER TABLE tenant_settings NO FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE tenant_settings DISABLE ROW LEVEL SECURITY")
    op.drop_table("tenant_settings")
