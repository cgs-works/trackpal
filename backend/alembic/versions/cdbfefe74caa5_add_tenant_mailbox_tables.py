"""Add tenant_mailboxes, mail_lookup_jobs, mail_code_delivery_log

Revision ID: cdbfefe74caa5
Revises: cdaefe74caa4
Create Date: 2026-05-27 10:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "cdbfefe74caa5"
down_revision: str | None = "cdaefe74caa4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # --- tenant_mailboxes ---
    op.create_table(
        "tenant_mailboxes",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("mailbox_email", sa.String(255), nullable=False),
        sa.Column("provider", sa.String(50), nullable=False),
        sa.Column("auth_method", sa.String(50), nullable=False),
        sa.Column(
            "status", sa.String(50), nullable=False, server_default="disconnected"
        ),
        # IMAP fields
        sa.Column("imap_host", sa.String(255), nullable=True),
        sa.Column("imap_port", sa.Integer(), nullable=True),
        sa.Column(
            "imap_ssl", sa.Boolean(), nullable=True, server_default=sa.text("true")
        ),
        sa.Column("imap_password_encrypted", sa.String(500), nullable=True),
        # OAuth fields
        sa.Column("oauth_provider_user_id", sa.String(255), nullable=True),
        sa.Column("oauth_provider_email", sa.String(255), nullable=True),
        sa.Column("oauth_access_token_encrypted", sa.String(2000), nullable=True),
        sa.Column("oauth_refresh_token_encrypted", sa.String(500), nullable=True),
        sa.Column("oauth_token_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("oauth_scope", sa.String(500), nullable=True),
        # Connection monitoring
        sa.Column("last_connection_test_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_connection_error", sa.String(1000), nullable=True),
        # Timestamps
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_tenant_mailboxes_tenant_id", "tenant_mailboxes", ["tenant_id"], unique=True
    )
    op.create_index("ix_tenant_mailboxes_status", "tenant_mailboxes", ["status"])

    # --- mail_lookup_jobs ---
    op.create_table(
        "mail_lookup_jobs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "mailbox_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenant_mailboxes.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("service_key", sa.String(64), nullable=False),
        sa.Column(
            "requested_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("result_type", sa.String(30), nullable=True),
        sa.Column("result_value_encrypted", sa.String(2000), nullable=True),
        sa.Column("error_code", sa.String(100), nullable=True),
        sa.Column("error_detail_safe", sa.String(1000), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("processing_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_mail_lookup_jobs_tenant_id", "mail_lookup_jobs", ["tenant_id"])
    op.create_index(
        "ix_mail_lookup_jobs_mailbox_id", "mail_lookup_jobs", ["mailbox_id"]
    )
    op.create_index("ix_mail_lookup_jobs_status", "mail_lookup_jobs", ["status"])
    op.create_index(
        "ix_mail_lookup_jobs_expires_at", "mail_lookup_jobs", ["expires_at"]
    )

    # --- mail_code_delivery_log ---
    op.create_table(
        "mail_code_delivery_log",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "mailbox_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenant_mailboxes.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("service_key", sa.String(64), nullable=False),
        sa.Column("message_id", sa.String(500), nullable=True),
        sa.Column("fingerprint", sa.String(128), nullable=False),
        sa.Column(
            "delivered_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_mail_code_delivery_log_tenant_id", "mail_code_delivery_log", ["tenant_id"]
    )
    op.create_index(
        "ix_mail_code_delivery_log_mailbox_id", "mail_code_delivery_log", ["mailbox_id"]
    )
    op.create_index(
        "ix_mail_code_delivery_log_fingerprint",
        "mail_code_delivery_log",
        [
            "tenant_id",
            "mailbox_id",
            "service_key",
            sa.text("substr(fingerprint, 1, 16)"),
        ],
    )

    # Unique composite constraint
    op.create_unique_constraint(
        "uq_mail_code_delivery_log",
        "mail_code_delivery_log",
        ["tenant_id", "mailbox_id", "service_key", "message_id", "fingerprint"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_mail_code_delivery_log", "mail_code_delivery_log", type_="unique"
    )
    op.drop_index(
        "ix_mail_code_delivery_log_fingerprint", table_name="mail_code_delivery_log"
    )
    op.drop_index(
        "ix_mail_code_delivery_log_mailbox_id", table_name="mail_code_delivery_log"
    )
    op.drop_index(
        "ix_mail_code_delivery_log_tenant_id", table_name="mail_code_delivery_log"
    )
    op.drop_table("mail_code_delivery_log")

    op.drop_index("ix_mail_lookup_jobs_expires_at", table_name="mail_lookup_jobs")
    op.drop_index("ix_mail_lookup_jobs_status", table_name="mail_lookup_jobs")
    op.drop_index("ix_mail_lookup_jobs_mailbox_id", table_name="mail_lookup_jobs")
    op.drop_index("ix_mail_lookup_jobs_tenant_id", table_name="mail_lookup_jobs")
    op.drop_table("mail_lookup_jobs")

    op.drop_index("ix_tenant_mailboxes_status", table_name="tenant_mailboxes")
    op.drop_index("ix_tenant_mailboxes_tenant_id", table_name="tenant_mailboxes")
    op.drop_table("tenant_mailboxes")
