"""Track the last successful executor protocol verification.

Revision ID: e024fe74cac4
Revises: e023fe74cac3
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e024fe74cac4"
down_revision: str | None = "e023fe74cac3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "lookup_executors",
        sa.Column("last_verified_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("lookup_executors", "last_verified_at")
