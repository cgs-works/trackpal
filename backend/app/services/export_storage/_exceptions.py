"""Custom exceptions for the export storage layer."""


class StorageObjectNotFoundError(Exception):
    """Raised when a storage object does not exist or cannot be found."""


class StorageOperationError(Exception):
    """Raised when a storage operation fails for a reason other than not-found."""
