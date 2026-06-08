"""Add evolution_instance_token to tenants

Revision ID: cdaefe74caa3
Revises: cd9efe74caa2
Create Date: 2026-05-25 10:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "cdaefe74caa3"
down_revision: Union[str, None] = "cd9efe74caa2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "tenants",
        sa.Column("evolution_instance_token", sa.String(length=500), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("tenants", "evolution_instance_token")
