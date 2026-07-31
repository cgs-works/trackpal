"""Remove Mailbox OAuth and the verification-only TrackPal Demo service.

Revision ID: e020fe74cac0
Revises: e019fe74cab9
Create Date: 2026-07-31 00:00:00.000000

The upgrade irreversibly deletes OAuth Mailbox rows and tenant selections for
trackpal_demo. The downgrade restores schema compatibility and the global
service row, but cannot reconstruct deleted credentials or selections.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e020fe74cac0"
down_revision: str | None = "e019fe74cab9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_OAUTH_COLUMNS = (
    "oauth_provider_user_id",
    "oauth_provider_email",
    "oauth_access_token_encrypted",
    "oauth_refresh_token_encrypted",
    "oauth_token_expires_at",
    "oauth_scope",
)


def upgrade() -> None:
    op.drop_constraint(
        "ck_tenant_mailboxes_auth_method",
        "tenant_mailboxes",
        type_="check",
    )
    op.execute("DELETE FROM tenant_mailboxes WHERE auth_method = 'oauth'")
    op.execute(
        "DELETE FROM tenant_code_service_selections "
        "WHERE service_key = 'trackpal_demo'"
    )
    op.execute(
        "DELETE FROM code_service_global_status "
        "WHERE service_key = 'trackpal_demo'"
    )
    for column in _OAUTH_COLUMNS:
        op.drop_column("tenant_mailboxes", column)
    op.drop_column("tenant_mailboxes", "auth_method")


def downgrade() -> None:
    op.add_column(
        "tenant_mailboxes",
        sa.Column("auth_method", sa.String(50), nullable=True),
    )
    op.execute("UPDATE tenant_mailboxes SET auth_method = 'app_password'")
    op.alter_column("tenant_mailboxes", "auth_method", nullable=False)

    op.add_column(
        "tenant_mailboxes",
        sa.Column("oauth_provider_user_id", sa.String(255), nullable=True),
    )
    op.add_column(
        "tenant_mailboxes",
        sa.Column("oauth_provider_email", sa.String(255), nullable=True),
    )
    op.add_column(
        "tenant_mailboxes",
        sa.Column("oauth_access_token_encrypted", sa.String(2000), nullable=True),
    )
    op.add_column(
        "tenant_mailboxes",
        sa.Column("oauth_refresh_token_encrypted", sa.String(500), nullable=True),
    )
    op.add_column(
        "tenant_mailboxes",
        sa.Column("oauth_token_expires_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "tenant_mailboxes",
        sa.Column("oauth_scope", sa.String(500), nullable=True),
    )
    op.create_check_constraint(
        "ck_tenant_mailboxes_auth_method",
        "tenant_mailboxes",
        "auth_method IN ('oauth', 'app_password')",
    )
    op.execute(
        "INSERT INTO code_service_global_status (service_key, is_active) "
        "VALUES ('trackpal_demo', true) "
        "ON CONFLICT (service_key) DO NOTHING"
    )
