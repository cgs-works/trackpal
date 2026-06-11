"""Upload diagnostic HTML to Cloudflare R2 (S3-compatible).

Only used when Netflix OTP extraction fails — saves the raw HTML response
for later debugging.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

import boto3
from botocore.config import Config as BotoConfig

from app.core.config import settings

logger = logging.getLogger(__name__)

_BOTO_CONFIG = BotoConfig(
    connect_timeout=5,
    read_timeout=10,
    retries={"max_attempts": 2, "mode": "standard"},
)


def _build_s3_client():
    """Build a boto3 S3 client from app settings.

    Returns ``None`` when R2 is not configured (allows graceful no-op).
    """
    if not settings.r2_endpoint_url or not settings.r2_access_key_id:
        logger.debug("R2 not configured — skipping diagnostic upload")
        return None
    return boto3.client(
        "s3",
        endpoint_url=settings.r2_endpoint_url,
        aws_access_key_id=settings.r2_access_key_id,
        aws_secret_access_key=settings.r2_secret_access_key,
        config=_BOTO_CONFIG,
    )


def upload_netflix_diagnostic(
    html_content: str,
    nftoken_prefix: str = "",
) -> str | None:
    """Upload Netflix verify HTML to R2 for debugging.

    Args:
        html_content: Raw HTML response body.
        nftoken_prefix: First 12 chars of the nftoken for traceability.

    Returns:
        Public URL of the uploaded object, or ``None`` on failure / no config.
    """
    client = _build_s3_client()
    if client is None:
        return None

    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S")
    safe_prefix = "".join(c for c in nftoken_prefix if c.isalnum())[:12]
    key = f"debug/netflix/verify_{timestamp}_{safe_prefix}.html"

    try:
        client.put_object(
            Bucket=settings.r2_bucket_name,
            Key=key,
            Body=html_content.encode("utf-8"),
            ContentType="text/html; charset=utf-8",
        )
        logger.info("Netflix diagnostic HTML uploaded to R2: %s", key)

        if settings.r2_public_url:
            return f"{settings.r2_public_url.rstrip('/')}/{key}"
        return key
    except Exception:
        logger.exception("Failed to upload Netflix diagnostic HTML to R2")
        return None


__all__ = [
    "upload_netflix_diagnostic",
]
