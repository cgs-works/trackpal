"""Add the synthetic TrackPal Demo code service.

Revision ID: e018fe74cab8
Revises: e017fe74cab7
Create Date: 2026-07-29 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e018fe74cab8"
down_revision: str | None = "e017fe74cab7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        sa.text(
            "INSERT INTO code_service_global_status (service_key, is_active) "
            "VALUES ('trackpal_demo', true) "
            "ON CONFLICT (service_key) DO NOTHING"
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            "DELETE FROM code_service_global_status WHERE service_key = 'trackpal_demo'"
        )
    )
