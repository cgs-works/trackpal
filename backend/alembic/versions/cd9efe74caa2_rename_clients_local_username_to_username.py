"""rename clients.local_username to username

Revision ID: cd9efe74caa2
Revises: cd8efe74caa1
Create Date: 2026-05-24 01:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "cd9efe74caa2"
down_revision: Union[str, Sequence[str], None] = "cd8efe74caa1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Drop index referencing old column name
    op.drop_index("ix_clients_tenant_lower_local_username", table_name="clients")

    # 2. Rename column
    op.alter_column("clients", "local_username", new_column_name="username")

    # 3. Re-create index with new column name
    op.create_index(
        "ix_clients_tenant_lower_username",
        "clients",
        ["tenant_id", sa.text("lower(username)")],
        unique=True,
        postgresql_using="btree",
    )

    # 4. Backfill canonical full username from users table
    op.execute(
        "UPDATE clients SET username = users.username "
        "FROM users WHERE clients.owner_user_id = users.id "
        "AND clients.username IS DISTINCT FROM users.username"
    )


def downgrade() -> None:
    op.drop_index("ix_clients_tenant_lower_username", table_name="clients")
    op.alter_column("clients", "username", new_column_name="local_username")
    op.create_index(
        "ix_clients_tenant_lower_local_username",
        "clients",
        ["tenant_id", sa.text("lower(local_username)")],
        unique=True,
    )
