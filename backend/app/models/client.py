import uuid

from sqlalchemy import Boolean, ForeignKey, Index, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class Client(Base, TimestampMixin):
    __tablename__ = "clients"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    owner_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    full_name: Mapped[str] = mapped_column(String(200), nullable=False)
    username: Mapped[str] = mapped_column(String(94), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    whatsapp_lid: Mapped[str | None] = mapped_column(String(100), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    __table_args__ = (
        UniqueConstraint("owner_user_id", name="uq_clients_owner_user_id"),
        Index(
            "ix_clients_tenant_lower_username",
            "tenant_id",
            func.lower(username),
            unique=True,
        ),
        Index("ix_clients_tenant_phone", "tenant_id", "phone", unique=True),
    )

    tenant = relationship("Tenant", back_populates="clients")
    user = relationship("User", back_populates="client_profile")
