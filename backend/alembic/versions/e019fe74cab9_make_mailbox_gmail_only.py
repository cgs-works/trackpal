"""Make mailbox Gmail-only — remove IMAP columns, add constraint.

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
    # Delete unsupported mailbox rows before tightening the auth-method contract.
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

    # Rename the Gmail app-password authentication method.
    op.execute("""
        UPDATE tenant_mailboxes
        SET auth_method = 'app_password'
        WHERE auth_method = 'imap_app_password'
    """)

    # Rename the encrypted credential column to match the new method name.
    op.alter_column(
        "tenant_mailboxes",
        "imap_password_encrypted",
        new_column_name="app_password_encrypted",
    )

    # Gmail server settings are fixed, so per-mailbox server columns are obsolete.
    op.drop_column("tenant_mailboxes", "imap_host")
    op.drop_column("tenant_mailboxes", "imap_port")
    op.drop_column("tenant_mailboxes", "imap_ssl")

    # Provider is no longer needed — auth_method alone identifies the connection type.
    op.drop_column("tenant_mailboxes", "provider")

    # Restrict mailbox authentication to the two Gmail connection methods.
    op.create_check_constraint(
        "ck_tenant_mailboxes_auth_method",
        "tenant_mailboxes",
        "auth_method IN ('oauth', 'app_password')",
    )


def downgrade() -> None:
    # Drop the constraint first so legacy values can be restored.
    op.drop_constraint(
        "ck_tenant_mailboxes_auth_method",
        "tenant_mailboxes",
        type_="check",
    )

    # Restore the removed Gmail server columns as nullable.
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

    # Restore provider as nullable initially (populated below, then made NOT NULL).
    op.add_column(
        "tenant_mailboxes",
        sa.Column("provider", sa.String(50), nullable=True),
    )

    # Repopulate Gmail server values for app-password rows.
    op.execute("""
        UPDATE tenant_mailboxes
        SET imap_host = 'imap.gmail.com',
            imap_port = 993,
            imap_ssl = true
        WHERE auth_method = 'app_password'
    """)

    # Restore the legacy app-password authentication method name.
    op.execute("""
        UPDATE tenant_mailboxes
        SET auth_method = 'imap_app_password'
        WHERE auth_method = 'app_password'
    """)

    # Restore the legacy encrypted credential column name.
    op.alter_column(
        "tenant_mailboxes",
        "app_password_encrypted",
        new_column_name="imap_password_encrypted",
    )

    # Restore provider values from the authentication method.
    op.execute("""
        UPDATE tenant_mailboxes
        SET provider = 'google'
        WHERE auth_method = 'oauth'
    """)
    op.execute("""
        UPDATE tenant_mailboxes
        SET provider = 'imap_custom'
        WHERE auth_method = 'imap_app_password'
    """)

    # Make provider NOT NULL now that all rows are populated.
    op.alter_column(
        "tenant_mailboxes",
        "provider",
        nullable=False,
    )
