"""Real Cloudflare R2 (S3-compatible) export storage adapter."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import boto3
from botocore.config import Config as BotoConfig
from botocore.exceptions import ClientError

from ._config import ExportStorageConfig
from ._exceptions import StorageObjectNotFoundError, StorageOperationError
from ._protocol import ExportStorageAdapter, ExportStorageMetadata

logger = logging.getLogger(__name__)

_BOTO_CONFIG = BotoConfig(
    signature_version="s3v4",
    connect_timeout=5,
    read_timeout=10,
    retries={"max_attempts": 2, "mode": "standard"},
)

_LOGGED_URLS: set[int] = set()


class R2ExportStorageAdapter(ExportStorageAdapter):
    """Production adapter backed by Cloudflare R2 (S3-compatible API).

    All network calls are dispatched to a thread-pool executor so the adapter
    can be used from async contexts without blocking the event loop.
    """

    def __init__(self, config: ExportStorageConfig) -> None:
        self._config = config
        self._client: Any = None  # lazy-created boto3 client

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _lazy_client(self) -> Any:
        if self._client is None:
            self._client = boto3.client(
                "s3",
                endpoint_url=self._config.endpoint_url,
                aws_access_key_id=self._config.access_key_id,
                aws_secret_access_key=self._config.secret_access_key,
                config=_BOTO_CONFIG,
            )
        return self._client

    async def _run(self, call: str, **kwargs: Any) -> Any:
        """Run a boto3 method in a thread-pool executor."""
        client = self._lazy_client()
        method = getattr(client, call)
        return await asyncio.to_thread(method, **kwargs)

    def _raise_on_missing(self, key: str, exc: ClientError) -> None:
        """Raise ``StorageObjectNotFoundError`` for 404 responses."""
        error_code = exc.response["Error"]["Code"]
        if error_code == "NoSuchKey" or error_code == "404":
            raise StorageObjectNotFoundError(f"Object not found: {key}") from exc
        raise StorageOperationError(str(exc)) from exc

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    async def upload(
        self,
        key: str,
        data: bytes,
        content_type: str = "application/octet-stream",
    ) -> None:
        try:
            await self._run(
                "put_object",
                Bucket=self._config.bucket_name,
                Key=key,
                Body=data,
                ContentType=content_type,
            )
            logger.info("Export object uploaded: %s (%d bytes)", key, len(data))
        except ClientError as exc:
            logger.exception("Failed to upload export object: %s", key)
            raise StorageOperationError(str(exc)) from exc

    async def get_metadata(self, key: str) -> ExportStorageMetadata:
        try:
            response = await self._run(
                "head_object", Bucket=self._config.bucket_name, Key=key
            )
            return ExportStorageMetadata(
                key=key,
                size_bytes=response.get("ContentLength", 0),
                content_type=response.get("ContentType", "application/octet-stream"),
                etag=response.get("ETag"),
            )
        except ClientError as exc:
            self._raise_on_missing(key, exc)

    async def delete(self, key: str) -> None:
        """Delete the object. Idempotent — missing keys are silently accepted."""
        try:
            await self._run("delete_object", Bucket=self._config.bucket_name, Key=key)
            logger.info("Export object deleted: %s", key)
        except ClientError as exc:
            logger.exception("Failed to delete export object: %s", key)
            raise StorageOperationError(str(exc)) from exc

    async def generate_presigned_get(
        self,
        key: str,
        expires_in_seconds: int,
        download_filename: str | None = None,
    ) -> str:
        try:
            params: dict[str, Any] = {
                "Bucket": self._config.bucket_name,
                "Key": key,
            }
            if download_filename:
                params["ResponseContentDisposition"] = (
                    f'attachment; filename="{download_filename}"'
                )

            url = await asyncio.to_thread(
                self._lazy_client().generate_presigned_url,
                "get_object",
                Params=params,
                ExpiresIn=expires_in_seconds,
            )

            # Log the fact that we generated a URL, but never the URL itself
            url_hash = hash(url)
            if url_hash not in _LOGGED_URLS:
                _LOGGED_URLS.add(url_hash)
                logger.info(
                    "Presigned GET generated for %s (expires_in=%ds, hash=%d)",
                    key,
                    expires_in_seconds,
                    url_hash,
                )

            return url
        except ClientError as exc:
            self._raise_on_missing(key, exc)


__all__ = [
    "R2ExportStorageAdapter",
]
