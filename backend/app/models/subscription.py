import uuid
from datetime import date, datetime
from typing import Any, Optional
from sqlalchemy import Boolean, ForeignKey, String, DateTime, Date, JSON
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import UniqueConstraint

from app.models.base import Base, TimestampMixin


class Subscription(Base, TimestampMixin):
    __tablename__ = "subscriptions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    client_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clients.id", ondelete="CASCADE"), nullable=False
    )
    service_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("services.id", ondelete="CASCADE"),
        nullable=False,
    )
    plan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("plans.id", ondelete="CASCADE"), nullable=False
    )

    streaming_email: Mapped[str] = mapped_column(String(255), nullable=False)
    streaming_password_encrypted: Mapped[Optional[str]] = mapped_column(
        String(500), nullable=True
    )
    profile_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    profile_pin_encrypted: Mapped[Optional[str]] = mapped_column(
        String(500), nullable=True
    )
    duration_type: Mapped[str] = mapped_column(String(50), nullable=False)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    cancelled_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    status: Mapped[str] = mapped_column(
        String(50), default="active", server_default="active", nullable=False
    )

    tenant = relationship("Tenant")
    client = relationship("Client")
    service = relationship("Service")
    plan = relationship("Plan")

    events = relationship(
        "SubscriptionEvent", back_populates="subscription", cascade="all, delete-orphan"
    )
    reminder_logs = relationship(
        "SubscriptionReminderLog",
        back_populates="subscription",
        cascade="all, delete-orphan",
    )


class SubscriptionEvent(Base, TimestampMixin):
    __tablename__ = "subscription_events"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    subscription_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("subscriptions.id", ondelete="CASCADE"),
        nullable=False,
    )
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    event_metadata: Mapped[Optional[Any]] = mapped_column(
        "metadata", JSON, nullable=True
    )

    tenant = relationship("Tenant")
    subscription = relationship("Subscription", back_populates="events")


class SubscriptionReminderLog(Base, TimestampMixin):
    __tablename__ = "subscription_reminder_logs"
    __table_args__ = (
        UniqueConstraint(
            "subscription_id",
            "days_before_expiry",
            "sent_for_date",
            "recipient_type",
            name="uq_subscription_reminder_dedupe",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    subscription_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("subscriptions.id", ondelete="CASCADE"),
        nullable=False,
    )
    recipient_type: Mapped[str] = mapped_column(String(50), nullable=False)
    recipient_phone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    days_before_expiry: Mapped[int] = mapped_column(nullable=False)
    sent_for_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(
        String(50), default="pending", server_default="pending", nullable=False
    )
    attempt_count: Mapped[int] = mapped_column(
        default=0, server_default="0", nullable=False
    )
    last_error: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    sent_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    tenant = relationship("Tenant")
    subscription = relationship("Subscription", back_populates="reminder_logs")


class SubscriptionReminderSettings(Base, TimestampMixin):
    __tablename__ = "subscription_reminder_settings"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    warning_days: Mapped[Any] = mapped_column(
        JSON, default=lambda: [7, 3, 1], server_default="[7, 3, 1]", nullable=False
    )
    reminder_time: Mapped[str] = mapped_column(
        String(5), default="09:00", server_default="09:00", nullable=False
    )
    recipient_mode: Mapped[str] = mapped_column(
        String(50), default="tenant_only", server_default="tenant_only", nullable=False
    )
    reminders_enabled: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=sa.text("false"), nullable=False
    )
    custom_message_tenant: Mapped[Optional[str]] = mapped_column(
        String(2000), nullable=True
    )
    custom_message_client: Mapped[Optional[str]] = mapped_column(
        String(2000), nullable=True
    )

    tenant = relationship("Tenant")
