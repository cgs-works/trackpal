import uuid

from sqlalchemy import ForeignKey, JSON, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class TenantApiKey(Base, TimestampMixin):
    __tablename__ = "tenant_api_keys"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        primary_key=True,
    )
    api_key: Mapped[str] = mapped_column(String(128), unique=True, index=True, nullable=False)
    allowed_origins: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)

    tenant = relationship("Tenant", back_populates="api_key")
