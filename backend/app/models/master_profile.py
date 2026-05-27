import uuid

from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class MasterProfile(Base, TimestampMixin):
    __tablename__ = "master_profiles"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(50), unique=True, nullable=True)
    whatsapp_lid: Mapped[str | None] = mapped_column(
        String(100), unique=True, nullable=True
    )

    user = relationship("User", back_populates="master_profile")
