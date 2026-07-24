"""Add Demo Tenant lifecycle persistence fields and constraints.

Revision ID: e017fe74cab7
Revises: e016fe74cab6
Create Date: 2026-07-25 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e017fe74cab7"
down_revision: str | None = "e016fe74cab6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


DEMO_LIFECYCLE_PAIR_CONSTRAINT = "ck_tenants_demo_lifecycle_pair"
DEMO_LIFECYCLE_ORDER_CONSTRAINT = "ck_tenants_demo_lifecycle_order"
DEMO_PRODUCTION_DEFAULTS_CONSTRAINT = "ck_tenants_demo_production_defaults"
DEMO_CREDENTIALS_VERSION_CONSTRAINT = "ck_tenants_demo_credentials_version"
DEMO_LIFECYCLE_INDEX = "ix_tenants_demo_lifecycle"


def upgrade() -> None:
    op.add_column(
        "tenants",
        sa.Column(
            "is_demo",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.add_column(
        "tenants",
        sa.Column("demo_activated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "tenants",
        sa.Column("demo_expires_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "tenants",
        sa.Column(
            "demo_credentials_version",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("1"),
        ),
    )

    op.create_check_constraint(
        DEMO_LIFECYCLE_PAIR_CONSTRAINT,
        "tenants",
        "(demo_activated_at IS NULL AND demo_expires_at IS NULL) OR "
        "(demo_activated_at IS NOT NULL AND demo_expires_at IS NOT NULL)",
    )
    op.create_check_constraint(
        DEMO_LIFECYCLE_ORDER_CONSTRAINT,
        "tenants",
        "demo_activated_at IS NULL OR demo_expires_at > demo_activated_at",
    )
    op.create_check_constraint(
        DEMO_PRODUCTION_DEFAULTS_CONSTRAINT,
        "tenants",
        "is_demo OR (demo_activated_at IS NULL AND demo_expires_at IS NULL "
        "AND demo_credentials_version = 1)",
    )
    op.create_check_constraint(
        DEMO_CREDENTIALS_VERSION_CONSTRAINT,
        "tenants",
        "demo_credentials_version >= 1",
    )
    op.create_index(
        DEMO_LIFECYCLE_INDEX,
        "tenants",
        ["is_demo", "demo_expires_at"],
    )


def downgrade() -> None:
    op.drop_constraint(DEMO_CREDENTIALS_VERSION_CONSTRAINT, "tenants", type_="check")
    op.drop_constraint(DEMO_PRODUCTION_DEFAULTS_CONSTRAINT, "tenants", type_="check")
    op.drop_constraint(DEMO_LIFECYCLE_ORDER_CONSTRAINT, "tenants", type_="check")
    op.drop_constraint(DEMO_LIFECYCLE_PAIR_CONSTRAINT, "tenants", type_="check")
    op.drop_index(DEMO_LIFECYCLE_INDEX, table_name="tenants")
    op.drop_column("tenants", "demo_credentials_version")
    op.drop_column("tenants", "demo_expires_at")
    op.drop_column("tenants", "demo_activated_at")
    op.drop_column("tenants", "is_demo")
