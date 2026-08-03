"""Remove the obsolete tenant contact email.

Revision ID: e026fe74cac6
Revises: e025fe74cac5
Create Date: 2026-08-04 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e026fe74cac6"
down_revision: Union[str, Sequence[str], None] = "e025fe74cac5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column("tenants", "email")


def downgrade() -> None:
    op.add_column(
        "tenants",
        sa.Column("email", sa.String(length=255), nullable=True),
    )
