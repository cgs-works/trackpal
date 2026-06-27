import uuid

from sqlalchemy import ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class BlockedClient(Base, TimestampMixin):
    """Tenant-scoped block for unregistered WhatsApp identities.

    At least one identity field (phone or whatsapp_lid) must be
    provided at creation — enforced by the repository layer.
    A row represents an active block; unblocking deletes the row.
    """

    __tablename__ = "blocked_clients"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    whatsapp_lid: Mapped[str | None] = mapped_column(String(100), nullable=True)

    __table_args__ = (
        Index("ix_blocked_clients_tenant_phone", "tenant_id", "phone"),
        Index("ix_blocked_clients_tenant_lid", "tenant_id", "whatsapp_lid"),
    )
