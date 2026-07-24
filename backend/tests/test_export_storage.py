"""Tests for R2 diagnostic and Tenant Data Export storage boundaries (Issue #98).

Verifies:
1. Settings validation and isolation for export storage.
2. Export storage adapter interface and Cloudflare R2 / S3 implementation.
3. Deterministic fake storage adapter for testing.
4. Non-leakage of PII in object keys and safe presigned GET generation.
5. Isolation/non-crossing between public diagnostic R2 config and private export storage config.
"""

from urllib.parse import parse_qs, urlsplit

import pytest

from app.core.config import Settings
from app.services.export_storage import (
    ExportStorageConfig,
    FakeExportStorageAdapter,
    R2ExportStorageAdapter,
    StorageObjectNotFoundError,
    StorageOperationError,
    generate_random_export_key,
)

pytestmark = pytest.mark.asyncio


class TestExportStorageSettings:
    """Test settings declarations and strict boundaries for export storage."""

    def test_export_storage_config_from_settings(self):
        settings = Settings(
            export_r2_access_key_id="export_key_id",
            export_r2_secret_access_key="export_secret",
            export_r2_bucket_name="trackpal-exports-private",
            export_r2_endpoint_url="https://account.r2.cloudflarestorage.com",
            export_signed_url_ttl_seconds=900,
        )
        config = ExportStorageConfig.from_settings(settings)
        assert config.access_key_id == "export_key_id"
        assert config.secret_access_key == "export_secret"
        assert config.bucket_name == "trackpal-exports-private"
        assert config.endpoint_url == "https://account.r2.cloudflarestorage.com"
        assert config.signed_url_ttl_seconds == 900

    def test_missing_export_storage_config_fails_validation(self):
        settings = Settings()
        assert not settings.is_export_storage_configured
        with pytest.raises(ValueError, match="Export storage is not configured"):
            ExportStorageConfig.from_settings(settings)

    def test_partial_export_config_fails_validation(self):
        settings = Settings(
            export_r2_access_key_id="export_key_id",
            # missing secret, bucket, endpoint
        )
        assert not settings.is_export_storage_configured
        with pytest.raises(ValueError, match="Export storage is not configured"):
            ExportStorageConfig.from_settings(settings)

    def test_export_storage_never_falls_back_to_diagnostic_r2(self):
        """Even if diagnostic R2 settings are populated, export storage must fail if its own settings are missing."""
        settings = Settings(
            r2_access_key_id="diag_key",
            r2_secret_access_key="diag_secret",
            r2_bucket_name="trackpal-debug",
            r2_endpoint_url="https://diag.r2.cloudflarestorage.com",
            r2_public_url="https://debug.trackpal.pages.dev",
        )
        assert not settings.is_export_storage_configured
        with pytest.raises(ValueError, match="Export storage is not configured"):
            ExportStorageConfig.from_settings(settings)

    def test_export_storage_rejects_public_url(self):
        """Export storage config must prohibit a public custom domain / public URL."""
        settings = Settings(
            export_r2_access_key_id="key",
            export_r2_secret_access_key="secret",
            export_r2_bucket_name="bucket",
            export_r2_endpoint_url="https://r2.example.com",
        )
        # Verify no public_url exists or is forbidden
        assert not hasattr(settings, "export_r2_public_url")


class TestRandomObjectKeyGeneration:
    """Test random object key formatting and absence of PII."""

    def test_generate_random_export_key_is_random_and_has_no_pii(self):
        key1 = generate_random_export_key()
        key2 = generate_random_export_key()

        assert key1 != key2
        assert len(key1) >= 32
        # Check no obvious sensitive strings or user identifiers
        assert "tenant" not in key1.lower()
        assert "user" not in key1.lower()
        assert "admin" not in key1.lower()
        assert "account" not in key1.lower()

    def test_key_format_is_safe_for_s3(self):
        key = generate_random_export_key()
        # Should be alphanumeric or hyphen/underscore or hex/uuid
        assert all(c.isalnum() or c in "-_/" for c in key)


class TestR2ExportStorageAdapter:
    async def test_presigned_get_uses_signature_v4(self):
        adapter = R2ExportStorageAdapter(
            ExportStorageConfig(
                access_key_id="test-access-key",
                secret_access_key="test-secret-key",
                bucket_name="trackpal-exports-private",
                endpoint_url="https://account.r2.cloudflarestorage.com",
            )
        )

        url = await adapter.generate_presigned_get(
            key="exports/test.zip",
            expires_in_seconds=900,
        )
        query = parse_qs(urlsplit(url).query)

        assert query["X-Amz-Algorithm"] == ["AWS4-HMAC-SHA256"]
        assert "AWSAccessKeyId" not in query


class TestFakeExportStorageAdapter:
    """Test deterministic fake storage adapter behavior."""

    @pytest.fixture
    def fake_adapter(self) -> FakeExportStorageAdapter:
        return FakeExportStorageAdapter()

    async def test_upload_and_metadata_lookup(
        self, fake_adapter: FakeExportStorageAdapter
    ):
        content = b"ZIP_DATA_BYTES"
        key = generate_random_export_key()

        await fake_adapter.upload(key=key, data=content, content_type="application/zip")

        meta = await fake_adapter.get_metadata(key)
        assert meta.key == key
        assert meta.size_bytes == len(content)
        assert meta.content_type == "application/zip"

    async def test_metadata_not_found(self, fake_adapter: FakeExportStorageAdapter):
        with pytest.raises(StorageObjectNotFoundError):
            await fake_adapter.get_metadata("nonexistent_key")

    async def test_delete_success_and_idempotency(
        self, fake_adapter: FakeExportStorageAdapter
    ):
        key = generate_random_export_key()
        await fake_adapter.upload(key=key, data=b"data")

        # First delete succeeds
        await fake_adapter.delete(key)

        # Second delete does not crash (idempotent / no-op or clean)
        await fake_adapter.delete(key)

        with pytest.raises(StorageObjectNotFoundError):
            await fake_adapter.get_metadata(key)

    async def test_presigned_url_generation(
        self, fake_adapter: FakeExportStorageAdapter
    ):
        key = generate_random_export_key()
        await fake_adapter.upload(key=key, data=b"data")

        url = await fake_adapter.generate_presigned_get(
            key=key,
            expires_in_seconds=900,
            download_filename="export-20250101.zip",
        )
        assert "export-20250101.zip" in url
        assert key in url

    async def test_presigned_url_for_missing_object_raises_not_found(
        self, fake_adapter: FakeExportStorageAdapter
    ):
        with pytest.raises(StorageObjectNotFoundError):
            await fake_adapter.generate_presigned_get(
                key="missing_key",
                expires_in_seconds=900,
                download_filename="export.zip",
            )

    async def test_simulated_transient_failure(
        self, fake_adapter: FakeExportStorageAdapter
    ):
        fake_adapter.simulate_failure(StorageOperationError("Transient S3 error"))

        with pytest.raises(StorageOperationError, match="Transient S3 error"):
            await fake_adapter.upload(key="key", data=b"data")

        # After clearing failure, operates normally
        fake_adapter.clear_simulated_failures()
        await fake_adapter.upload(key="key", data=b"data")
