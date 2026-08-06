"""Mailbox configuration schemas for tenant dashboard and n8n integration."""

from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


# --- Enums ---


class MailboxStatus(str, Enum):
    disconnected = "disconnected"
    connected = "connected"
    error = "error"


class LookupJobStatus(str, Enum):
    pending = "pending"
    processing = "processing"
    completed = "completed"
    failed = "failed"
    timeout = "timeout"


class LookupResultType(str, Enum):
    code = "code"
    url = "url"
    not_found = "not_found"
    duplicate_suppressed = "duplicate_suppressed"


# --- Gmail-only connect schema ---


class GmailAppPasswordConnectRequest(BaseModel):
    """Payload for connecting a Gmail mailbox via app password."""

    mailbox_email: str = Field(min_length=3, max_length=255)
    app_password: str = Field(min_length=1, max_length=500)


# --- Tenant dashboard schemas ---


class MailboxResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    mailbox_email: str
    status: str
    last_connection_test_at: datetime | None = None
    last_connection_error: str | None = None
    created_at: datetime
    updated_at: datetime


class MailboxTestRequest(BaseModel):
    model_config = ConfigDict()


class MailboxTestResponse(BaseModel):
    success: bool
    message: str


# --- n8n lookup schemas ---


class LookupCreateRequest(BaseModel):
    model_config = ConfigDict()

    service_key: str = Field(min_length=1, max_length=64)
    tenant_instance: str | None = Field(
        None,
        max_length=255,
        description="Evolution API instance name to resolve tenant",
    )
    tenant_id: UUID | None = Field(
        None, description="Direct tenant ID (alternative to tenant_instance)"
    )
    mailbox_email: str | None = Field(
        None, max_length=255, description="Optional filter by mailbox email"
    )
    target_email: str = Field(
        min_length=3,
        max_length=255,
        description="Target email to filter email content during extraction — required for code lookup",
    )


class LookupCreateResponse(BaseModel):
    job_id: UUID
    status: str = "pending"


class LookupResumeRequest(BaseModel):
    tenant_id: UUID
    resume_url: str = Field(min_length=1, max_length=2048)


class LookupStatusResponse(BaseModel):
    job_id: UUID
    status: str
    result_type: str | None = None
    result_value: str | None = None
    error_code: str | None = None
    error_detail: str | None = None
    reply: str | None = None
    created_at: datetime | None = None
    completed_at: datetime | None = None
