"""Remove is_active from blocked_clients.

Revision ID: e013fe74cab3
Revises: e012fe74cab2
Create Date: 2026-06-27 00:00:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "e013fe74cab3"
down_revision: str | None = "e012fe74cab2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("DELETE FROM blocked_clients WHERE is_active IS FALSE")
    op.drop_column("blocked_clients", "is_active")


def downgrade() -> None:
    op.add_column(
        "blocked_clients",
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
    )
