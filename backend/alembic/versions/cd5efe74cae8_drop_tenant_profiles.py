"""drop legacy tenant profiles

Revision ID: cd5efe74cae8
Revises: cd4efe74cae7
Create Date: 2026-05-17 17:35:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "cd5efe74cae8"
down_revision: Union[str, Sequence[str], None] = "cd4efe74cae7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_table("tenant_profiles")


def downgrade() -> None:
    op.create_table(
        "tenant_profiles",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("full_name", sa.String(length=200), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("phone", sa.String(length=50), nullable=True),
        sa.Column("evolution_instance_name", sa.String(length=200), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
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
        sa.ForeignKeyConstraint(["id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("phone"),
    )
    op.execute(
        """
        INSERT INTO tenant_profiles (
            id, full_name, email, phone, evolution_instance_name, is_active, created_at, updated_at
        )
        SELECT owner_user_id, name, email, whatsapp_phone, evolution_instance_name, is_active, created_at, updated_at
        FROM tenants
        """
    )
