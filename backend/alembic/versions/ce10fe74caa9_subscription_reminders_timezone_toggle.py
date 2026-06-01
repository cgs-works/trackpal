"""Add reminders_enabled column to subscription_reminder_settings.

Revision ID: ce10fe74caa9
Revises: cdc0fe74caa8
Create Date: 2026-05-31 12:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "ce10fe74caa9"
down_revision: str | None = "cdc0fe74caa8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "subscription_reminder_settings",
        sa.Column(
            "reminders_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )


def downgrade() -> None:
    op.drop_column("subscription_reminder_settings", "reminders_enabled")
