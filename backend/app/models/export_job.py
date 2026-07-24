"""Tenant-scoped durable export job model.

Stores lifecycle metadata for Tenant Data Export artifacts — never ZIP
bytes or exported field values.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class ExportJob(Base, TimestampMixin):
    """A single Tenant Data Export generation attempt.

    Each row represents one logical export generation lifecycle.  Status
    transitions follow::

        pending → processing → ready
          │                     │
          └→ cancelled    failed←┘

    A `ready` job is superseded when a new successful generation replaces
    it; the previous row remains for the ready-object download window.
    """

    __tablename__ = "export_jobs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    requested_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    # ── Lifecycle ──────────────────────────────────────────────
    status: Mapped[str] = mapped_column(
        String(20), default="pending", nullable=False, index=True
    )
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3, nullable=False)

    # ── Worker lease ───────────────────────────────────────────
    lease_token: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    lease_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # ── Artifact metadata ──────────────────────────────────────
    r2_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    r2_uploaded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    artifact_size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # ── Timing ─────────────────────────────────────────────────
    ready_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # ── Error ──────────────────────────────────────────────────
    error_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    error_detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    failed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # ── Cooldown ───────────────────────────────────────────────
    cooldown_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # ── Actor attribution ──────────────────────────────────────
    actor_role: Mapped[str | None] = mapped_column(String(10), nullable=True)

    # ── Replacement chain ──────────────────────────────────────
    replaced_job_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    replacement_job_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )

    # ── Relationships ──────────────────────────────────────────
    tenant = relationship(
        "Tenant",
        back_populates="export_jobs",
        passive_deletes=True,
    )


__all__ = [
    "ExportJob",
]
