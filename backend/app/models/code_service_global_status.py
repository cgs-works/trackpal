"""Global activation status for code lookup services (master-controlled)."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class CodeServiceGlobalStatus(Base, TimestampMixin):
    """One row per globally supported code service.

    Master activates/deactivates services here.  Tenant selections
    reference these keys; only globally active + tenant-selected
    services appear in WhatsApp code flow.
    """

    __tablename__ = "code_service_global_status"

    service_key: Mapped[str] = mapped_column(String(50), primary_key=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False, server_default=text("true")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=text("now()"),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=text("now()"),
        nullable=False,
    )
