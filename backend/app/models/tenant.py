from __future__ import annotations

import secrets
import string
import uuid
from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class DemoTenantStatus(str, Enum):
    """Lifecycle status derived from a Demo Tenant's persisted timestamps."""

    PENDING = "pending"
    ACTIVE = "active"
    EXPIRED = "expired"


def _default_client_prefix() -> str:
    alphabet = string.ascii_lowercase
    tail = string.ascii_lowercase + string.digits
    return secrets.choice(alphabet) + "".join(secrets.choice(tail) for _ in range(4))


def _as_utc(value: datetime) -> datetime:
    """Normalize database timestamps before comparing them with server time."""
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


class Tenant(Base, TimestampMixin):
    __tablename__ = "tenants"
    __table_args__ = (
        CheckConstraint(
            "(demo_activated_at IS NULL AND demo_expires_at IS NULL) OR "
            "(demo_activated_at IS NOT NULL AND demo_expires_at IS NOT NULL)",
            name="ck_tenants_demo_lifecycle_pair",
        ),
        CheckConstraint(
            "demo_activated_at IS NULL OR demo_expires_at > demo_activated_at",
            name="ck_tenants_demo_lifecycle_order",
        ),
        CheckConstraint(
            "is_demo OR (demo_activated_at IS NULL AND demo_expires_at IS NULL "
            "AND demo_credentials_version = 1)",
            name="ck_tenants_demo_production_defaults",
        ),
        CheckConstraint(
            "demo_credentials_version >= 1",
            name="ck_tenants_demo_credentials_version",
        ),
        CheckConstraint(
            "demo_locale IS NULL OR demo_locale IN ('en', 'es')",
            name="ck_tenants_demo_locale_values",
        ),
        CheckConstraint(
            "is_demo OR demo_locale IS NULL",
            name="ck_tenants_production_demo_locale",
        ),
        Index("ix_tenants_demo_lifecycle", "is_demo", "demo_expires_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    owner_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    client_prefix: Mapped[str] = mapped_column(
        String(5), unique=True, nullable=False, default=_default_client_prefix
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    whatsapp_phone: Mapped[str | None] = mapped_column(
        String(50), unique=True, nullable=True
    )
    evolution_instance_name: Mapped[str | None] = mapped_column(
        String(200), unique=True, nullable=True
    )
    evolution_instance_token: Mapped[str | None] = mapped_column(
        String(500), nullable=True
    )
    whatsapp_lid: Mapped[str | None] = mapped_column(
        String(100), unique=True, nullable=True
    )
    plan: Mapped[str] = mapped_column(String(20), default="pro", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_demo: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", nullable=False
    )
    demo_activated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    demo_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    demo_credentials_version: Mapped[int] = mapped_column(
        Integer, default=1, server_default="1", nullable=False
    )
    demo_locale: Mapped[str | None] = mapped_column(String(10), nullable=True)

    owner = relationship("User", back_populates="owned_tenant")
    clients = relationship(
        "Client", back_populates="tenant", cascade="all, delete-orphan"
    )
    services = relationship(
        "Service", back_populates="tenant", cascade="all, delete-orphan"
    )
    plans = relationship("Plan", back_populates="tenant", cascade="all, delete-orphan")
    settings = relationship(
        "TenantSettings",
        back_populates="tenant",
        cascade="all, delete-orphan",
        uselist=False,
        lazy="selectin",
    )
    api_key = relationship(
        "TenantApiKey",
        back_populates="tenant",
        cascade="all, delete-orphan",
        uselist=False,
    )
    help_acknowledgements = relationship(
        "TenantHelpAcknowledgement",
        back_populates="tenant",
        cascade="all, delete-orphan",
    )
    export_jobs = relationship(
        "ExportJob",
        back_populates="tenant",
        passive_deletes=True,
    )

    def get_demo_status(self, now: datetime | None = None) -> DemoTenantStatus | None:
        """Derive lifecycle status from timestamps using authoritative server time."""
        if not self.is_demo:
            return None
        if self.demo_activated_at is None:
            return DemoTenantStatus.PENDING
        if self.demo_expires_at is None:
            raise ValueError("Demo Tenant lifecycle timestamps are incomplete")

        current_time = _as_utc(now or datetime.now(timezone.utc))
        return (
            DemoTenantStatus.EXPIRED
            if current_time >= _as_utc(self.demo_expires_at)
            else DemoTenantStatus.ACTIVE
        )

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
