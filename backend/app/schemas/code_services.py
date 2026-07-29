"""Schemas for code-service global status and tenant selection APIs."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


# ── Supported service catalog (source of truth in code) ──────────────────

# Alphabetical by visible label — matches STREAMING_SERVICE_KEYS order.
SUPPORTED_CODE_SERVICES: dict[str, str] = {
    "disney": "Disney+",
    "hbo_max": "HBO Max",
    "netflix": "Netflix",
    "prime_video": "Prime Video",
    "spotify": "Spotify",
    "trackpal_demo": "TrackPal Demo",
    "universal_plus": "Universal+",
}

VALID_SERVICE_KEYS: frozenset[str] = frozenset(SUPPORTED_CODE_SERVICES.keys())


# ── Global status ────────────────────────────────────────────────────────


class CodeServiceGlobalItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    service_key: str
    label: str
    is_active: bool


class CodeServiceGlobalListResponse(BaseModel):
    services: list[CodeServiceGlobalItem]


class CodeServiceGlobalUpdateRequest(BaseModel):
    """Master toggles global active status for a service."""

    is_active: bool


class CodeServiceGlobalBulkUpdateRequest(BaseModel):
    """Master sets all global statuses in one call."""

    services: dict[str, bool] = Field(
        ...,
        description="Mapping of service_key → is_active",
    )

    def validate_keys(self) -> None:
        invalid = set(self.services.keys()) - VALID_SERVICE_KEYS
        if invalid:
            raise ValueError(
                f"Invalid service_key(s): {', '.join(sorted(invalid))}. "
                f"Valid keys: {', '.join(sorted(VALID_SERVICE_KEYS))}"
            )


# ── Tenant selection ─────────────────────────────────────────────────────


class TenantCodeServiceItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    service_key: str
    label: str
    is_selected: bool
    is_globally_active: bool


class TenantCodeServiceListResponse(BaseModel):
    tenant_id: str
    services: list[TenantCodeServiceItem]


class TenantCodeServiceUpdateRequest(BaseModel):
    """Tenant/master sets selected code services for a tenant.

    Full-replace sync: the provided list becomes the new selection.
    """

    service_keys: list[str] = Field(
        ...,
        min_length=0,
        description="List of service_keys to select (empty = deselect all)",
    )

    def validate_keys(self) -> None:
        invalid = set(self.service_keys) - VALID_SERVICE_KEYS
        if invalid:
            raise ValueError(
                f"Invalid service_key(s): {', '.join(sorted(invalid))}. "
                f"Valid keys: {', '.join(sorted(VALID_SERVICE_KEYS))}"
            )
