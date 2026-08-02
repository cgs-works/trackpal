"""Persisted registry entry for a trusted external mail lookup executor."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Index, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class LookupExecutor(Base, TimestampMixin):
    """Master-managed connection and lifecycle metadata for an executor."""

    __tablename__ = "lookup_executors"
    __table_args__ = (
        Index("ix_lookup_executors_lifecycle_status", "lifecycle_status"),
        Index("ix_lookup_executors_health_status", "health_status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    provider_label: Mapped[str] = mapped_column(String(50), nullable=False)
    base_url: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    transport_mode: Mapped[str] = mapped_column(
        String(30), nullable=False, default="https", server_default="https"
    )
    lifecycle_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="draft", server_default="draft"
    )
    health_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="unknown", server_default="unknown"
    )
    requires_reverification: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    max_concurrency: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default="1"
    )

    secret_encrypted: Mapped[str] = mapped_column(String(500), nullable=False)
    secret_version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default="1"
    )
    pending_secret_encrypted: Mapped[str | None] = mapped_column(
        String(500), nullable=True
    )
    pending_secret_version: Mapped[int | None] = mapped_column(Integer, nullable=True)

    hosting_account_email: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )
    hosting_account_password_encrypted: Mapped[str | None] = mapped_column(
        String(500), nullable=True
    )
    dashboard_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    last_health_check_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_success_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_error_safe: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    jobs = relationship("MailLookupJob", back_populates="executor")


__all__ = ["LookupExecutor"]
