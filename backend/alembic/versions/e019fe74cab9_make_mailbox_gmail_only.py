"""Make mailbox Gmail-only — remove provider/IMAP columns, add constraint.

Revision ID: e019fe74cab9
Revises: e018fe74cab8
Create Date: 2026-07-30 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e019fe74cab9"
down_revision: str | None = "e018fe74cab8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Delete non-Gmail rows
    op.execute("""
        DELETE FROM tenant_mailboxes
        WHERE NOT (
          (provider = 'google' AND auth_method = 'oauth')
          OR (
            provider = 'imap_custom'
            AND auth_method = 'imap_app_password'
            AND lower(imap_host) = 'imap.gmail.com'
            AND coalesce(imap_port, 993) = 993
            AND coalesce(imap_ssl, true) = true
          )
        )
    """)

    # 2. Map imap_app_password -> app_password
    op.execute("""
        UPDATE tenant_mailboxes
        SET auth_method = 'app_password'
        WHERE auth_method = 'imap_app_password'
    """)

    # 3. Rename credential column
    op.alter_column(
        "tenant_mailboxes",
        "imap_password_encrypted",
        new_column_name="app_password_encrypted",
    )

    # 4. Drop provider/server columns
    op.drop_column("tenant_mailboxes", "imap_host")
    op.drop_column("tenant_mailboxes", "imap_port")
    op.drop_column("tenant_mailboxes", "imap_ssl")
    op.drop_column("tenant_mailboxes", "provider")

    # 5. Add auth_method check constraint
    op.create_check_constraint(
        "ck_tenant_mailboxes_auth_method",
        "tenant_mailboxes",
        "auth_method IN ('oauth', 'app_password')",
    )


def downgrade() -> None:
    # 1. Drop the check constraint first so restoration is not blocked
    op.drop_constraint(
        "ck_tenant_mailboxes_auth_method",
        "tenant_mailboxes",
        type_="check",
    )

    # 2. Restore dropped columns as nullable
    op.add_column(
        "tenant_mailboxes",
        sa.Column("provider", sa.String(50), nullable=True),
    )
    op.add_column(
        "tenant_mailboxes",
        sa.Column("imap_host", sa.String(255), nullable=True),
    )
    op.add_column(
        "tenant_mailboxes",
        sa.Column("imap_port", sa.Integer(), nullable=True),
    )
    op.add_column(
        "tenant_mailboxes",
        sa.Column("imap_ssl", sa.Boolean(), server_default="true", nullable=True),
    )

    # 3. Derive provider values from auth_method
    op.execute("""
        UPDATE tenant_mailboxes
        SET provider = 'google'
        WHERE auth_method = 'oauth'
    """)
    op.execute("""
        UPDATE tenant_mailboxes
        SET provider = 'imap_custom'
        WHERE auth_method = 'app_password'
    """)

    # 4. Restore Gmail server values for app-password rows
    op.execute("""
        UPDATE tenant_mailboxes
        SET imap_host = 'imap.gmail.com',
            imap_port = 993,
            imap_ssl = true
        WHERE auth_method = 'app_password'
    """)

    # 5. Map app_password back to imap_app_password
    op.execute("""
        UPDATE tenant_mailboxes
        SET auth_method = 'imap_app_password'
        WHERE auth_method = 'app_password'
    """)

    # 6. Rename encrypted column back
    op.alter_column(
        "tenant_mailboxes",
        "app_password_encrypted",
        new_column_name="imap_password_encrypted",
    )

    # 7. Make provider non-null after population
    op.alter_column(
        "tenant_mailboxes",
        "provider",
        nullable=False,
        server_default="google",
    )
