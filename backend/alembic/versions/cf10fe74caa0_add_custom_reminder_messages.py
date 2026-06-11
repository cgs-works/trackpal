"""Add custom message fields to subscription reminder settings.

Revision ID: cf10fe74caa0
Revises: ce10fe74caa9
Create Date: 2026-06-11
"""

from alembic import op
import sqlalchemy as sa

revision = "cf10fe74caa0"
down_revision = "ce10fe74caa9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "subscription_reminder_settings",
        sa.Column("custom_message_tenant", sa.String(2000), nullable=True),
    )
    op.add_column(
        "subscription_reminder_settings",
        sa.Column("custom_message_client", sa.String(2000), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("subscription_reminder_settings", "custom_message_tenant")
    op.drop_column("subscription_reminder_settings", "custom_message_client")
