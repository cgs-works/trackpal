"""Add whatsapp_lid columns for LID/JID identity resolution

Revision ID: cdaefe74caa4
Revises: cdaefe74caa3
Create Date: 2026-05-26 10:00:00.000000

"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "cdaefe74caa4"
down_revision: str | None = "cdaefe74caa3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # master_profiles
    op.add_column(
        "master_profiles",
        sa.Column("whatsapp_lid", sa.String(100), nullable=True),
    )
    op.create_index(
        "ix_master_profiles_whatsapp_lid",
        "master_profiles",
        ["whatsapp_lid"],
        unique=True,
    )

    # tenants
    op.add_column(
        "tenants",
        sa.Column("whatsapp_lid", sa.String(100), nullable=True),
    )
    op.create_index(
        "ix_tenants_whatsapp_lid",
        "tenants",
        ["whatsapp_lid"],
        unique=True,
    )

    # clients
    op.add_column(
        "clients",
        sa.Column("whatsapp_lid", sa.String(100), nullable=True),
    )
    op.create_index(
        "ix_clients_whatsapp_lid",
        "clients",
        ["whatsapp_lid"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_clients_whatsapp_lid", table_name="clients")
    op.drop_column("clients", "whatsapp_lid")
    op.drop_index("ix_tenants_whatsapp_lid", table_name="tenants")
    op.drop_column("tenants", "whatsapp_lid")
    op.drop_index("ix_master_profiles_whatsapp_lid", table_name="master_profiles")
    op.drop_column("master_profiles", "whatsapp_lid")
