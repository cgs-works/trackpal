import secrets
import string
import uuid

from sqlalchemy import Boolean, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


def _default_client_prefix() -> str:
    alphabet = string.ascii_lowercase
    tail = string.ascii_lowercase + string.digits
    return secrets.choice(alphabet) + "".join(secrets.choice(tail) for _ in range(4))


class Tenant(Base, TimestampMixin):
    __tablename__ = "tenants"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    owner_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    client_prefix: Mapped[str] = mapped_column(
        String(5), unique=True, nullable=False, default=_default_client_prefix
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    whatsapp_phone: Mapped[str | None] = mapped_column(String(50), unique=True, nullable=True)
    evolution_instance_name: Mapped[str | None] = mapped_column(String(200), unique=True, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    owner = relationship("User", back_populates="owned_tenant")
    clients = relationship("Client", back_populates="tenant", cascade="all, delete-orphan")
    services = relationship("Service", back_populates="tenant", cascade="all, delete-orphan")
    plans = relationship("Plan", back_populates="tenant", cascade="all, delete-orphan")

    @property
    def full_name(self) -> str:
        return self.name

    @full_name.setter
    def full_name(self, value: str) -> None:
        self.name = value

    @property
    def phone(self) -> str | None:
        return self.whatsapp_phone

    @phone.setter
    def phone(self, value: str | None) -> None:
        self.whatsapp_phone = value
