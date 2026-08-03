"""Add the initial locale for browser-local Demo Workspaces.

Revision ID: e025fe74cac5
Revises: e024fe74cac4
Create Date: 2026-08-04 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e025fe74cac5"
down_revision: Union[str, Sequence[str], None] = "e024fe74cac4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


DEMO_LOCALE_VALUES_CONSTRAINT = "ck_tenants_demo_locale_values"
PRODUCTION_DEMO_LOCALE_CONSTRAINT = "ck_tenants_production_demo_locale"


def upgrade() -> None:
    op.add_column(
        "tenants", sa.Column("demo_locale", sa.String(length=10), nullable=True)
    )
    op.create_check_constraint(
        DEMO_LOCALE_VALUES_CONSTRAINT,
        "tenants",
        "demo_locale IS NULL OR demo_locale IN ('en', 'es')",
    )
    op.create_check_constraint(
        PRODUCTION_DEMO_LOCALE_CONSTRAINT,
        "tenants",
        "is_demo OR demo_locale IS NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        PRODUCTION_DEMO_LOCALE_CONSTRAINT,
        "tenants",
        type_="check",
    )
    op.drop_constraint(
        DEMO_LOCALE_VALUES_CONSTRAINT,
        "tenants",
        type_="check",
    )
    op.drop_column("tenants", "demo_locale")
