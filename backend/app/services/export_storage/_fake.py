"""Deterministic fake export storage adapter for higher-level tests."""

from __future__ import annotations

from datetime import UTC, datetime

from ._exceptions import StorageObjectNotFoundError, StorageOperationError
from ._protocol import ExportStorageAdapter, ExportStorageMetadata


class _StoredObject:
    """In-memory representation of a stored object."""

    def __init__(
        self,
        key: str,
        data: bytes,
        content_type: str,
    ) -> None:
        self.key = key
        self.data = data
        self.content_type = content_type
        self.uploaded_at = datetime.now(UTC)


class FakeExportStorageAdapter(ExportStorageAdapter):
    """Deterministic in-memory fake for testing.

    Supports failure simulation so higher-level tests can exercise error
    paths without touching real R2 credentials.
    """

    def __init__(self) -> None:
        self._store: dict[str, _StoredObject] = {}
        self._failure: StorageOperationError | None = None

    # ------------------------------------------------------------------
    # Failure simulation
    # ------------------------------------------------------------------

    def simulate_failure(self, exc: StorageOperationError) -> None:
        """Make the next storage operation raise *exc*."""
        self._failure = exc

    def clear_simulated_failures(self) -> None:
        """Reset failure simulation — subsequent calls behave normally."""
        self._failure = None

    # ------------------------------------------------------------------
    # Helpers for test assertions
    # ------------------------------------------------------------------

    @property
    def stored_keys(self) -> set[str]:
        """Return the set of keys currently in the store."""
        return set(self._store)

    # ------------------------------------------------------------------
    # ExportStorageAdapter interface
    # ------------------------------------------------------------------

    async def upload(
        self,
        key: str,
        data: bytes,
        content_type: str = "application/octet-stream",
    ) -> None:
        self._check_failure()
        self._store[key] = _StoredObject(
            key=key,
            data=data,
            content_type=content_type,
        )

    async def get_metadata(self, key: str) -> ExportStorageMetadata:
        self._check_failure()
        obj = self._store.get(key)
        if obj is None:
            raise StorageObjectNotFoundError(f"Object not found: {key}")
        return ExportStorageMetadata(
            key=obj.key,
            size_bytes=len(obj.data),
            content_type=obj.content_type,
            uploaded_at=obj.uploaded_at,
        )

    async def delete(self, key: str) -> None:
        self._check_failure()
        # Idempotent — discard silently if not present
        self._store.pop(key, None)

    async def generate_presigned_get(
        self,
        key: str,
        expires_in_seconds: int,
        download_filename: str | None = None,
    ) -> str:
        self._check_failure()
        obj = self._store.get(key)
        if obj is None:
            raise StorageObjectNotFoundError(f"Object not found: {key}")

        # Build a deterministic fake URL that tests can assert on
        parts = [key, str(expires_in_seconds)]
        if download_filename:
            parts.append(download_filename)
        return f"https://fake-export-storage.example.com/{'/'.join(parts)}"

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _check_failure(self) -> None:
        if self._failure is not None:
            raise self._failure


__all__ = [
    "FakeExportStorageAdapter",
]
