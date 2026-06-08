"""Mailbox configuration schemas for tenant dashboard and n8n integration."""

from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


# --- Enums ---


class MailboxProvider(str, Enum):
    google = "google"
    microsoft = "microsoft"
    imap_custom = "imap_custom"


class MailboxAuthMethod(str, Enum):
    oauth = "oauth"
    imap_app_password = "imap_app_password"


class MailboxStatus(str, Enum):
    disconnected = "disconnected"
    connected = "connected"
    error = "error"
    revoked = "revoked"


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


# --- Tenant dashboard schemas ---


class MailboxConfigUpdate(BaseModel):
    model_config = ConfigDict()

    provider: MailboxProvider
    mailbox_email: str = Field(min_length=1, max_length=255)

    # IMAP fields (required when provider=imap_custom)
    imap_host: str | None = Field(None, max_length=255)
    imap_port: int | None = Field(None, ge=1, le=65535)
    imap_ssl: bool | None = True
    imap_password: str | None = Field(None, min_length=1, max_length=500)

    @model_validator(mode="after")
    def validate_imap_fields(self):
        if self.provider == MailboxProvider.imap_custom:
            missing = []
            if not self.imap_host:
                missing.append("imap_host")
            if not self.imap_port:
                missing.append("imap_port")
            if not self.imap_password:
                missing.append("imap_password")
            if missing:
                raise ValueError(f"IMAP fields required: {', '.join(missing)}")
        return self


class MailboxResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    mailbox_email: str
    provider: str
    auth_method: str
    status: str
    oauth_provider_user_id: str | None = None
    oauth_provider_email: str | None = None
    imap_host: str | None = None
    imap_port: int | None = None
    imap_ssl: bool | None = None
    last_connection_test_at: datetime | None = None
    last_connection_error: str | None = None
    created_at: datetime
    updated_at: datetime


class MailboxTestRequest(BaseModel):
    model_config = ConfigDict()


class MailboxTestResponse(BaseModel):
    success: bool
    message: str


class OAuthStartResponse(BaseModel):
    auth_url: str
    state: str


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


class LookupStatusResponse(BaseModel):
    job_id: UUID
    status: str
    result_type: str | None = None
    result_value: str | None = None
    error_code: str | None = None
    error_detail: str | None = None
    created_at: datetime | None = None
    completed_at: datetime | None = None
