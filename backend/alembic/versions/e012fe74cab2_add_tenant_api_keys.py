"""add tenant api keys

Revision ID: e012fe74cab2
Revises: e011fe74cab1
Create Date: 2026-06-27 00:00:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "e012fe74cab2"
down_revision: str | Sequence[str] | None = "e011fe74cab1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "tenant_api_keys",
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("api_key", sa.String(length=128), nullable=False),
        sa.Column("allowed_origins", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("tenant_id"),
    )
    op.create_index("ix_tenant_api_keys_api_key", "tenant_api_keys", ["api_key"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_tenant_api_keys_api_key", table_name="tenant_api_keys")
    op.drop_table("tenant_api_keys")
