# Phase 8: Lifecycle Flows

**Complexity:** M
**Dependencies:** Phase 5

## Objective

- Implement safe WhatsApp flows for deactivating, reactivating, and deleting Tenants using existing Trackpal lifecycle rules.

## Preconditions

- Tenant list/select/detail flow works.
- Selected Tenant identity is available in Redis.
- Existing TenantService deactivate, activate, and delete behavior is available.

## Tasks

1. Context: inspect Tenant lifecycle service behavior and existing lifecycle tests.
2. Implement: route main menu option `3` to a deactivation selection flow.
3. Implement: route main menu option `4` to a delete selection flow.
4. Implement: expose deactivate/reactivate actions from the selected Tenant detail screen.
5. Implement: require textual `CONFIRMAR` before deactivation.
6. Implement: require textual `CONFIRMAR` before deletion.
7. Implement: block deletion of active Tenants and explain that they must be deactivated first.
8. Implement: allow deletion only for inactive Tenants after confirmation.
9. Implement: support reactivation for inactive Tenants from the detail screen.
10. Implement: clear or update Redis session after successful lifecycle action.
11. Test: cover deactivation confirmation and cancellation.
12. Test: cover reactivation of inactive Tenant.
13. Test: cover attempted deletion of active Tenant.
14. Test: cover confirmed deletion of inactive Tenant.
15. Test: cover invalid confirmation text and reset behavior.
16. Verify: run lifecycle tests and full backend suite.

## Verification

- Commands:
  - `cd backend && uv run pytest backend/tests/test_whatsapp_lifecycle_flow.py -v`
  - `cd backend && uv run pytest -v`
- Expected results:
  - Deactivation requires `CONFIRMAR` and then deactivates the Tenant.
  - Reactivation restores inactive Tenant access according to existing lifecycle rules.
  - Active Tenants cannot be deleted.
  - Inactive Tenants can be deleted only after `CONFIRMAR`.
  - Destructive action tests do not send real WhatsApp messages.

## Exit Criteria

- Lifecycle flows comply with existing Trackpal Tenant rules.
- Destructive actions require explicit textual confirmation.
- Tests cover success, blocked, invalid, and cancellation paths.
- Full backend suite passes.
