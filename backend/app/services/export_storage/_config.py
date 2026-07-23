"""Configuration for the isolated Tenant Data Export storage."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ExportStorageConfig:
    """Dedicated private-bucket configuration for Tenant Data Export.

    Every field is required at runtime — missing settings must be detected
    eagerly and never default to the public diagnostic R2 configuration.
    """

    access_key_id: str
    secret_access_key: str
    bucket_name: str
    endpoint_url: str
    signed_url_ttl_seconds: int = 900

    @classmethod
    def from_settings(cls, settings: object) -> ExportStorageConfig:
        """Build config from a ``Settings`` instance.

        Raises ``ValueError`` when any required field is missing or empty,
        even if the diagnostic R2 settings are fully populated.
        """
        if (
            not hasattr(settings, "is_export_storage_configured")
            or not settings.is_export_storage_configured
        ):  # type: ignore[union-attr]
            msg = "Export storage is not configured"
            raise ValueError(msg)

        return cls(
            access_key_id=settings.export_r2_access_key_id,  # type: ignore[union-attr]
            secret_access_key=settings.export_r2_secret_access_key,  # type: ignore[union-attr]
            bucket_name=settings.export_r2_bucket_name,  # type: ignore[union-attr]
            endpoint_url=settings.export_r2_endpoint_url,  # type: ignore[union-attr]
            signed_url_ttl_seconds=getattr(
                settings, "export_signed_url_ttl_seconds", 900
            ),
        )


__all__ = [
    "ExportStorageConfig",
]
