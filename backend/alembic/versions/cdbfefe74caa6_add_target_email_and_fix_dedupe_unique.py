"""Add target_email to mail_lookup_jobs, fix dedupe unique constraint for null message_id

PostgreSQL unique constraints treat NULL values as distinct, so
(tenant_id, mailbox_id, service_key, NULL, fingerprint) could appear
multiple times.  Replace the constraint with two partial unique indexes:

1. When ``message_id IS NOT NULL`` — unique across all 5 columns.
2. When ``message_id IS NULL`` — unique across 4 columns (ignore message_id).

Also adds an optional ``target_email`` column to ``mail_lookup_jobs``
for recipient-based filtering during code extraction.

Revision ID: cdbfefe74caa6
Revises: cdbfefe74caa5
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "cdbfefe74caa6"
down_revision: str | None = "cdbfefe74caa5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # --- Add target_email to mail_lookup_jobs ---
    op.add_column(
        "mail_lookup_jobs",
        sa.Column("target_email", sa.String(255), nullable=True),
    )
    op.create_index(
        "ix_mail_lookup_jobs_target_email",
        "mail_lookup_jobs",
        ["target_email"],
    )

    # --- Fix dedupe unique constraint for null message_id ---
    # PostgreSQL unique constraints treat NULL != NULL, so the existing
    # constraint allows duplicate rows when message_id IS NULL.
    # Drop and replace with two partial unique indexes.

    op.drop_constraint(
        "uq_mail_code_delivery_log",
        "mail_code_delivery_log",
        type_="unique",
    )

    # Index for non-null message_id: unique across all 5 columns
    op.create_index(
        "uq_mail_code_delivery_log_w_msgid",
        "mail_code_delivery_log",
        ["tenant_id", "mailbox_id", "service_key", "message_id", "fingerprint"],
        unique=True,
        postgresql_where=sa.text("message_id IS NOT NULL"),
    )

    # Index for null message_id: unique across 4 columns (message_id excluded)
    op.create_index(
        "uq_mail_code_delivery_log_no_msgid",
        "mail_code_delivery_log",
        ["tenant_id", "mailbox_id", "service_key", "fingerprint"],
        unique=True,
        postgresql_where=sa.text("message_id IS NULL"),
    )


def downgrade() -> None:
    # --- Restore original unique constraint ---
    op.drop_index(
        "uq_mail_code_delivery_log_no_msgid",
        table_name="mail_code_delivery_log",
    )
    op.drop_index(
        "uq_mail_code_delivery_log_w_msgid",
        table_name="mail_code_delivery_log",
    )
    op.create_unique_constraint(
        "uq_mail_code_delivery_log",
        "mail_code_delivery_log",
        ["tenant_id", "mailbox_id", "service_key", "message_id", "fingerprint"],
    )

    # --- Drop target_email column ---
    op.drop_index("ix_mail_lookup_jobs_target_email", table_name="mail_lookup_jobs")
    op.drop_column("mail_lookup_jobs", "target_email")
