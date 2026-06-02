import uuid

from sqlalchemy import Boolean, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class ClientMessagingBlock(Base, TimestampMixin):
    """Tenant-scoped block for unregistered WhatsApp identities.

    At least one identity field (phone or whatsapp_lid) must be
    provided at creation — enforced by the repository layer.
    """

    __tablename__ = "client_messaging_blocks"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    whatsapp_lid: Mapped[str | None] = mapped_column(String(100), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    __table_args__ = (
        Index("ix_cmb_tenant_phone", "tenant_id", "phone"),
        Index("ix_cmb_tenant_lid", "tenant_id", "whatsapp_lid"),
    )
