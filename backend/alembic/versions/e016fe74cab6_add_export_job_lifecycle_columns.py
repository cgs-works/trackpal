"""Add lifecycle columns to export jobs.

Revision ID: e016fe74cab6
Revises: e015fe74cab5
Create Date: 2026-07-24 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e016fe74cab6"
down_revision: str | None = "e015fe74cab5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "export_jobs",
        sa.Column("failed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "export_jobs",
        sa.Column("cooldown_until", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "export_jobs",
        sa.Column("actor_role", sa.String(10), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("export_jobs", "actor_role")
    op.drop_column("export_jobs", "cooldown_until")
    op.drop_column("export_jobs", "failed_at")
