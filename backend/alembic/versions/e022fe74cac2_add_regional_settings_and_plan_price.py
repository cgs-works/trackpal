"""Add country/currency to tenant_settings and price to plans

Revision ID: e022fe74cac2
Revises: e021fe74cac1
Create Date: 2026-08-01 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e022fe74cac2"
down_revision: str | None = "e021fe74cac1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "tenant_settings", sa.Column("country", sa.String(length=2), nullable=True)
    )
    op.add_column(
        "tenant_settings", sa.Column("currency", sa.String(length=3), nullable=True)
    )
    op.add_column("plans", sa.Column("price", sa.Numeric(12, 2), nullable=True))


def downgrade() -> None:
    op.drop_column("plans", "price")
    op.drop_column("tenant_settings", "currency")
    op.drop_column("tenant_settings", "country")
