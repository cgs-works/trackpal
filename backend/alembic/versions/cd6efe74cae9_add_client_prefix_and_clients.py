"""add client prefixes and clients table

Revision ID: cd6efe74cae9
Revises: cd5efe74cae8
Create Date: 2026-05-17 20:30:00.000000
"""

from typing import Sequence, Union
import secrets
import string

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "cd6efe74cae9"
down_revision: Union[str, Sequence[str], None] = "cd5efe74cae8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _generate_client_prefix(existing: set[str]) -> str:
    alphabet = string.ascii_lowercase
    tail = string.ascii_lowercase + string.digits
    for _ in range(100):
        prefix = secrets.choice(alphabet) + "".join(secrets.choice(tail) for _ in range(4))
        if prefix not in existing:
            existing.add(prefix)
            return prefix
    raise RuntimeError("Unable to generate unique client prefix")


def upgrade() -> None:
    op.add_column("tenants", sa.Column("client_prefix", sa.String(length=5), nullable=True))

    bind = op.get_bind()
    existing_prefixes = {
        row[0]
        for row in bind.execute(sa.text("SELECT client_prefix FROM tenants WHERE client_prefix IS NOT NULL")).all()
        if row[0]
    }
    tenant_ids = [
        row[0]
        for row in bind.execute(sa.text("SELECT id FROM tenants WHERE client_prefix IS NULL ORDER BY created_at, id")).all()
    ]
    for tenant_id in tenant_ids:
        prefix = _generate_client_prefix(existing_prefixes)
        bind.execute(
            sa.text("UPDATE tenants SET client_prefix = :prefix WHERE id = :tenant_id"),
            {"prefix": prefix, "tenant_id": tenant_id},
        )

    op.alter_column("tenants", "client_prefix", nullable=False)
    op.create_unique_constraint("uq_tenants_client_prefix", "tenants", ["client_prefix"])

    op.create_table(
        "clients",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("owner_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("full_name", sa.String(length=200), nullable=False),
        sa.Column("local_username", sa.String(length=94), nullable=False),
        sa.Column("phone", sa.String(length=50), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("owner_user_id", name="uq_clients_owner_user_id"),
    )
    op.create_index(
        "ix_clients_tenant_lower_local_username",
        "clients",
        ["tenant_id", sa.text("lower(local_username)")],
        unique=True,
    )
    op.create_index("ix_clients_tenant_phone", "clients", ["tenant_id", "phone"], unique=True)

    op.execute("ALTER TABLE clients ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE clients FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY clients_tenant_isolation ON clients
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
                    WHERE t.id = clients.tenant_id
                      AND t.owner_user_id::text = NULLIF(current_setting('app.current_user_id', true), '')
                      AND t.is_active
                )
            )
            OR (
                current_setting('app.current_role', true) = 'client'
                AND owner_user_id::text = NULLIF(current_setting('app.current_user_id', true), '')
                AND is_active
                AND EXISTS (
                    SELECT 1
                    FROM tenants t
                    WHERE t.id = clients.tenant_id
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
                    WHERE t.id = clients.tenant_id
                      AND t.owner_user_id::text = NULLIF(current_setting('app.current_user_id', true), '')
                      AND t.is_active
                )
            )
            OR (
                current_setting('app.current_role', true) = 'client'
                AND false
            )
        )
        """
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS clients_tenant_isolation ON clients")
    op.execute("ALTER TABLE clients NO FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE clients DISABLE ROW LEVEL SECURITY")
    op.drop_index("ix_clients_tenant_phone", table_name="clients")
    op.drop_index("ix_clients_tenant_lower_local_username", table_name="clients")
    op.drop_table("clients")
    op.drop_constraint("uq_tenants_client_prefix", "tenants", type_="unique")
    op.drop_column("tenants", "client_prefix")
