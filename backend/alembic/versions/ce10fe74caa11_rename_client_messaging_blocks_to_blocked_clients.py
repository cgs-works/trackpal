"""Rename client_messaging_blocks to blocked_clients.

Revision ID: ce10fe74caa11
Revises: ce10fe74caa10
Create Date: 2026-06-02 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "ce10fe74caa11"
down_revision: str | None = "ce10fe74caa10"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.rename_table("client_messaging_blocks", "blocked_clients")
    op.execute(
        "ALTER INDEX ix_cmb_tenant_phone "
        "RENAME TO ix_blocked_clients_tenant_phone"
    )
    op.execute(
        "ALTER INDEX ix_cmb_tenant_lid "
        "RENAME TO ix_blocked_clients_tenant_lid"
    )


def downgrade() -> None:
    op.execute(
        "ALTER INDEX ix_blocked_clients_tenant_phone "
        "RENAME TO ix_cmb_tenant_phone"
    )
    op.execute(
        "ALTER INDEX ix_blocked_clients_tenant_lid "
        "RENAME TO ix_cmb_tenant_lid"
    )
    op.rename_table("blocked_clients", "client_messaging_blocks")
