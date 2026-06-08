"""tenant catalog and rls

Revision ID: cd3efe74cae6
Revises: cd2efe74cae5
Create Date: 2026-05-17 16:06:09.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "cd3efe74cae6"
down_revision: Union[str, Sequence[str], None] = "cd2efe74cae5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "tenants",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("owner_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("whatsapp_phone", sa.String(length=50), nullable=True),
        sa.Column("evolution_instance_name", sa.String(length=200), nullable=True),
        sa.Column(
            "is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")
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
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("owner_user_id"),
        sa.UniqueConstraint("whatsapp_phone"),
        sa.UniqueConstraint("evolution_instance_name"),
    )
    op.execute(
        """
        INSERT INTO tenants (id, owner_user_id, name, email, whatsapp_phone, evolution_instance_name, is_active, created_at, updated_at)
        SELECT id, id, full_name, email, phone, evolution_instance_name, is_active, created_at, updated_at
        FROM tenant_profiles
        """
    )
    op.create_table(
        "services",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
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
        sa.UniqueConstraint("tenant_id", "id", name="uq_services_tenant_id_id"),
    )
    op.create_index(
        "ix_services_tenant_lower_name",
        "services",
        ["tenant_id", sa.text("lower(name)")],
        unique=True,
    )
    op.create_table(
        "plans",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("service_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
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
            ["tenant_id", "service_id"],
            ["services.tenant_id", "services.id"],
            ondelete="CASCADE",
            name="fk_plans_tenant_service",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_plans_tenant_service_lower_name",
        "plans",
        ["tenant_id", "service_id", sa.text("lower(name)")],
        unique=True,
    )

    op.execute("ALTER TABLE tenants ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE services ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE plans ENABLE ROW LEVEL SECURITY")
    for table in ("tenants", "services", "plans"):
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY tenants_tenant_isolation ON tenants
        USING (
            current_setting('app.current_role', true) = 'master'
            OR (current_setting('app.current_role', true) = 'tenant' AND owner_user_id::text = NULLIF(current_setting('app.current_user_id', true), '') AND is_active)
        )
        WITH CHECK (
            current_setting('app.current_role', true) = 'master'
            OR (current_setting('app.current_role', true) = 'tenant' AND owner_user_id::text = NULLIF(current_setting('app.current_user_id', true), ''))
        )
    """)
    op.execute("""
        CREATE POLICY services_tenant_isolation ON services
        USING (
            (current_setting('app.current_role', true) = 'master' AND tenant_id::text = NULLIF(current_setting('app.active_tenant_id', true), ''))
            OR (current_setting('app.current_role', true) = 'tenant' AND EXISTS (SELECT 1 FROM tenants t WHERE t.id = services.tenant_id AND t.owner_user_id::text = NULLIF(current_setting('app.current_user_id', true), '') AND t.is_active))
        )
        WITH CHECK (
            (current_setting('app.current_role', true) = 'master' AND tenant_id::text = NULLIF(current_setting('app.active_tenant_id', true), ''))
            OR (current_setting('app.current_role', true) = 'tenant' AND EXISTS (SELECT 1 FROM tenants t WHERE t.id = services.tenant_id AND t.owner_user_id::text = NULLIF(current_setting('app.current_user_id', true), '') AND t.is_active))
        )
    """)
    op.execute("""
        CREATE POLICY plans_tenant_isolation ON plans
        USING (
            (current_setting('app.current_role', true) = 'master' AND tenant_id::text = NULLIF(current_setting('app.active_tenant_id', true), ''))
            OR (current_setting('app.current_role', true) = 'tenant' AND EXISTS (SELECT 1 FROM tenants t WHERE t.id = plans.tenant_id AND t.owner_user_id::text = NULLIF(current_setting('app.current_user_id', true), '') AND t.is_active))
        )
        WITH CHECK (
            (current_setting('app.current_role', true) = 'master' AND tenant_id::text = NULLIF(current_setting('app.active_tenant_id', true), ''))
            OR (current_setting('app.current_role', true) = 'tenant' AND EXISTS (SELECT 1 FROM tenants t WHERE t.id = plans.tenant_id AND t.owner_user_id::text = NULLIF(current_setting('app.current_user_id', true), '') AND t.is_active))
        )
    """)


def downgrade() -> None:
    op.drop_table("plans")
    op.drop_table("services")
    op.drop_table("tenants")
