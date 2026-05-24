"""WhatsApp Master Console auth-gated facade."""

from .facade import WhatsAppMasterConsoleFacade
from .protocols import TenantServiceProtocol

__all__ = ["WhatsAppMasterConsoleFacade", "TenantServiceProtocol"]
