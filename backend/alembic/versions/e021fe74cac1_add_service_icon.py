"""Add optional Iconify reference to Catalog Services.

Revision ID: e021fe74cac1
Revises: e020fe74cac0
Create Date: 2026-07-31 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e021fe74cac1"
down_revision: str | None = "e020fe74cac0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("services", sa.Column("icon", sa.String(255), nullable=True))


def downgrade() -> None:
    op.drop_column("services", "icon")
