"""Tenant Data Export storage adapter — isolated private R2 boundary.

Provides a strict storage contract for Tenant Data Export ZIP objects,
completely independent from the public diagnostic R2 configuration.
"""

from ._config import ExportStorageConfig
from ._exceptions import StorageObjectNotFoundError, StorageOperationError
from ._keys import generate_random_export_key
from ._protocol import ExportStorageAdapter, ExportStorageMetadata
from ._r2 import R2ExportStorageAdapter
from ._fake import FakeExportStorageAdapter

__all__ = [
    "ExportStorageAdapter",
    "ExportStorageConfig",
    "ExportStorageMetadata",
    "FakeExportStorageAdapter",
    "R2ExportStorageAdapter",
    "StorageObjectNotFoundError",
    "StorageOperationError",
    "generate_random_export_key",
]
