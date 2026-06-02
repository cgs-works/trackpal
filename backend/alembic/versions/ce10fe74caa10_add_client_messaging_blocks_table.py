"""Add client_messaging_blocks table.

Revision ID: ce10fe74caa10
Revises: ce10fe74caa9
Create Date: 2026-06-01 22:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "ce10fe74caa10"
down_revision: str | None = "ce10fe74caa9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "client_messaging_blocks",
        sa.Column(
            "id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")
        ),
        sa.Column("tenant_id", sa.Uuid(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("phone", sa.String(50), nullable=True),
        sa.Column("whatsapp_lid", sa.String(100), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
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
    op.create_index("ix_cmb_tenant_phone", "client_messaging_blocks", ["tenant_id", "phone"])
    op.create_index("ix_cmb_tenant_lid", "client_messaging_blocks", ["tenant_id", "whatsapp_lid"])


def downgrade() -> None:
    op.drop_index("ix_cmb_tenant_lid")
    op.drop_index("ix_cmb_tenant_phone")
    op.drop_table("client_messaging_blocks")
