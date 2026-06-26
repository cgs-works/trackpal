from __future__ import annotations

from typing import Final, Literal

TenantPlan = Literal["starter", "pro"]
TENANT_PLAN_STARTER: Final[TenantPlan] = "starter"
TENANT_PLAN_PRO: Final[TenantPlan] = "pro"
VALID_TENANT_PLANS: Final[tuple[TenantPlan, TenantPlan]] = (
    TENANT_PLAN_STARTER,
    TENANT_PLAN_PRO,
)


def normalize_tenant_plan(value: str) -> TenantPlan:
    normalized = value.strip().lower()
    if normalized not in VALID_TENANT_PLANS:
        raise ValueError("Plan must be one of: starter, pro")
    return normalized  # type: ignore[return-value]
