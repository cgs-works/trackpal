"""add tenant locale column

Revision ID: cd8efe74caa1
Revises: cd7efe74caa0
Create Date: 2026-05-23 01:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "cd8efe74caa1"
down_revision: Union[str, Sequence[str], None] = "cd7efe74caa0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Step 1: add column as nullable
    op.add_column("tenants", sa.Column("locale", sa.String(length=10), nullable=True))
    # Step 2: backfill existing rows to 'es' (existing tenants keep Spanish)
    op.execute("UPDATE tenants SET locale = 'es' WHERE locale IS NULL")
    # Step 3: set not null with server default 'en' for new tenants
    op.alter_column("tenants", "locale", nullable=False, server_default=sa.text("'en'"))


def downgrade() -> None:
    op.drop_column("tenants", "locale")
