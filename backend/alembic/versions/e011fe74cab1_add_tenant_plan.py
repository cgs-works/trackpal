"""add tenant plan

Revision ID: e011fe74cab1
Revises: d011fe74cab0
Create Date: 2026-06-24 00:00:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "e011fe74cab1"
down_revision: str | Sequence[str] | None = "d011fe74cab0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


CHECK_NAME = "ck_tenants_plan_allowed"


def upgrade() -> None:
    op.add_column(
        "tenants",
        sa.Column("plan", sa.String(length=20), server_default="pro", nullable=False),
    )
    op.execute("UPDATE tenants SET plan = 'pro' WHERE plan IS NULL")
    op.create_check_constraint(
        CHECK_NAME,
        "tenants",
        "plan IN ('starter', 'pro')",
    )


def downgrade() -> None:
    op.drop_constraint(CHECK_NAME, "tenants", type_="check")
    op.drop_column("tenants", "plan")
