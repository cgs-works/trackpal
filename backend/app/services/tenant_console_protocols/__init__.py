"""Protocol definitions for tenant-console dependency injection."""

from .protocols import (
    CatalogServiceProtocol,
    ClientServiceProtocol,
    SubscriptionServiceProtocol,
)

__all__ = [
    "CatalogServiceProtocol",
    "ClientServiceProtocol",
    "SubscriptionServiceProtocol",
]
