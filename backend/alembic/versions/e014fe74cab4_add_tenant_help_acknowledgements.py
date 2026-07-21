"""Add Tenant-scoped Help tour acknowledgements.

Revision ID: e014fe74cab4
Revises: e013fe74cab3
Create Date: 2026-06-03 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "e014fe74cab4"
down_revision: str | None = "e013fe74cab3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "tenant_help_acknowledgements",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("release_id", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "release_id", name="uq_tenant_help_release"),
    )
    op.create_index(
        "ix_tenant_help_acknowledgements_tenant_id",
        "tenant_help_acknowledgements",
        ["tenant_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_tenant_help_acknowledgements_tenant_id",
        table_name="tenant_help_acknowledgements",
    )
    op.drop_table("tenant_help_acknowledgements")
