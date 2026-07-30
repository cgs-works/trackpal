import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class TenantMailbox(Base, TimestampMixin):
    __tablename__ = "tenant_mailboxes"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    mailbox_email: Mapped[str] = mapped_column(String(255), nullable=False)
    auth_method: Mapped[str] = mapped_column(String(50), nullable=False)
    # Legacy column retained for backward-compatible database migrations.
    provider: Mapped[str | None] = mapped_column(String(50), nullable=True)
    status: Mapped[str] = mapped_column(
        String(50),
        default="disconnected",
        server_default="disconnected",
        nullable=False,
    )

    # Gmail app-password credential
    app_password_encrypted: Mapped[str | None] = mapped_column(
        String(500), nullable=True
    )

    # OAuth fields
    oauth_provider_user_id: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )
    oauth_provider_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    oauth_access_token_encrypted: Mapped[str | None] = mapped_column(
        String(2000), nullable=True
    )
    oauth_refresh_token_encrypted: Mapped[str | None] = mapped_column(
        String(500), nullable=True
    )
    oauth_token_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    oauth_scope: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Connection monitoring
    last_connection_test_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_connection_error: Mapped[str | None] = mapped_column(
        String(1000), nullable=True
    )

    tenant = relationship("Tenant")
