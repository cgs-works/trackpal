import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Index, String, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class MailCodeDeliveryLog(Base):
    __tablename__ = "mail_code_delivery_log"

    __table_args__ = (
        Index(
            "uq_mail_code_delivery_log_w_msgid",
            "tenant_id",
            "mailbox_id",
            "service_key",
            "message_id",
            "fingerprint",
            unique=True,
            postgresql_where=text("message_id IS NOT NULL"),
            sqlite_where=text("message_id IS NOT NULL"),
        ),
        Index(
            "uq_mail_code_delivery_log_no_msgid",
            "tenant_id",
            "mailbox_id",
            "service_key",
            "fingerprint",
            unique=True,
            postgresql_where=text("message_id IS NULL"),
            sqlite_where=text("message_id IS NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    mailbox_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenant_mailboxes.id", ondelete="CASCADE"),
        nullable=False,
    )
    service_key: Mapped[str] = mapped_column(String(64), nullable=False)
    message_id: Mapped[str | None] = mapped_column(String(500), nullable=True)
    fingerprint: Mapped[str] = mapped_column(String(128), nullable=False)
    delivered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    tenant = relationship("Tenant")
    mailbox = relationship("TenantMailbox")
