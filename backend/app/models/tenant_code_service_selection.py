"""Per-tenant code service selection for code lookup flow."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, String, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class TenantCodeServiceSelection(Base):
    """Records which code services a tenant has selected.

    Full-replace sync: saving selections replaces all rows for the
    tenant in a single transaction (last-write-wins).
    """

    __tablename__ = "tenant_code_service_selections"
    __table_args__ = ({"schema": None},)

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        primary_key=True,
    )
    service_key: Mapped[str] = mapped_column(
        String(50),
        ForeignKey("code_service_global_status.service_key", ondelete="CASCADE"),
        primary_key=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=text("now()"),
        nullable=False,
    )
