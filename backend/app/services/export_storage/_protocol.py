"""Abstract storage adapter protocol and metadata types."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class ExportStorageMetadata:
    """Metadata for a stored export object."""

    key: str
    size_bytes: int
    content_type: str
    uploaded_at: datetime | None = None
    etag: str | None = None


class ExportStorageAdapter(ABC):
    """Interface for Tenant Data Export object storage.

    All methods are async to allow a thread-pool-wrapped synchronous S3 client
    or a fully async in-memory fake.
    """

    @abstractmethod
    async def upload(
        self,
        key: str,
        data: bytes,
        content_type: str = "application/octet-stream",
    ) -> None:
        """Store *data* at *key*."""

    @abstractmethod
    async def get_metadata(self, key: str) -> ExportStorageMetadata:
        """Return metadata for *key*.

        Raises ``StorageObjectNotFoundError`` when the object does not exist.
        """

    @abstractmethod
    async def delete(self, key: str) -> None:
        """Delete the object at *key*.

        Should be idempotent — calling delete on a non-existent key must not
        raise.
        """

    @abstractmethod
    async def generate_presigned_get(
        self,
        key: str,
        expires_in_seconds: int,
        download_filename: str | None = None,
    ) -> str:
        """Return a presigned GET URL for *key*.

        Raises ``StorageObjectNotFoundError`` when the object does not exist.
        The returned URL must never be logged.
        """


__all__ = [
    "ExportStorageAdapter",
    "ExportStorageMetadata",
]
