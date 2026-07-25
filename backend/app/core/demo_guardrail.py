"""Backend policy that keeps Demo Tenants out of production operations."""

from __future__ import annotations

import logging
from typing import Protocol
from uuid import UUID

logger = logging.getLogger(__name__)

DEMO_OPERATION_BLOCKED = "demo_operation_blocked"


class DemoTenantLike(Protocol):
    id: UUID
    is_demo: bool


class DemoGuardrailError(Exception):
    """Raised when a Demo Tenant reaches a production-only operation."""

    code = DEMO_OPERATION_BLOCKED

    def __init__(self, *, operation: str, tenant_id: UUID) -> None:
        self.operation = operation
        self.tenant_id = tenant_id
        super().__init__(self.code)


def assert_demo_operation_allowed(
    tenant: DemoTenantLike, *, operation: str
) -> None:
    """Reject production operations for Demo Tenants without touching side effects."""
    if not tenant.is_demo:
        return

    logger.info(
        "Demo guardrail rejected operation=%s tenant=%s",
        operation,
        tenant.id,
    )
    raise DemoGuardrailError(operation=operation, tenant_id=tenant.id)
