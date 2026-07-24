"""Service layer — business logic and orchestration for TrackPal."""

from app.services.auth_service import AuthService
from app.services.catalog_service import CatalogService
from app.services.client_service import ClientService
from app.services.contingency_reply_policy import ContingencyReplyPolicy
from app.services.export_storage import (
    ExportStorageAdapter,
    ExportStorageConfig,
    ExportStorageMetadata,
    FakeExportStorageAdapter,
    R2ExportStorageAdapter,
    StorageObjectNotFoundError,
    StorageOperationError,
    generate_random_export_key,
)
from app.services.profile_service import ProfileService
from app.services.tenant_console_protocols import (
    CatalogServiceProtocol,
    ClientServiceProtocol,
)
from app.services.tenant_service import TenantService
from app.services.whatsapp_console_service import WhatsAppConsoleService
from app.services.whatsapp_master_console_facade import WhatsAppMasterConsoleFacade
from app.services.whatsapp_session_service import WhatsAppSessionService
from app.services.whatsapp_tenant_console_facade import WhatsAppTenantConsoleFacade
from app.services.imap_service import ImapConnectionError, test_imap_connection
from app.services.oauth_service import MailboxOAuthService
from app.services.whatsapp_tenant_console_service import WhatsAppTenantConsoleService

__all__ = [
    "AuthService",
    "ImapConnectionError",
    "MailboxOAuthService",
    "test_imap_connection",
    "CatalogService",
    "CatalogServiceProtocol",
    "ClientService",
    "ClientServiceProtocol",
    "ContingencyReplyPolicy",
    "ExportStorageAdapter",
    "ExportStorageConfig",
    "ExportStorageMetadata",
    "FakeExportStorageAdapter",
    "ProfileService",
    "R2ExportStorageAdapter",
    "StorageObjectNotFoundError",
    "StorageOperationError",
    "generate_random_export_key",
    "TenantService",
    "WhatsAppConsoleService",
    "WhatsAppMasterConsoleFacade",
    "WhatsAppSessionService",
    "WhatsAppTenantConsoleFacade",
    "WhatsAppTenantConsoleService",
]
