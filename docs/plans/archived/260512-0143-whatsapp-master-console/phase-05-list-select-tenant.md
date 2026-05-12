# Phase 5: List and Select Tenant Flow

**Complexity:** M
**Dependencies:** Phase 4

## Objective

- Implement the Ver tenants flow with numbered Tenant selection, Redis-backed Tenant index maps, and a selected Tenant detail screen.

## Preconditions

- Main menu and reset behavior work.
- Existing TenantService list/get behavior is available.
- Redis session can store temporary maps.

## Tasks

1. Context: inspect TenantService list/get methods and Tenant response fields.
2. Implement: route main menu option `1` to list Tenants.
3. Implement: fetch active and inactive Tenants through existing backend service behavior.
4. Implement: format Tenants as a numbered list with clear active/inactive status.
5. Implement: store number-to-Tenant identity map in Redis for the Master session.
6. Implement: set session flow/step to await Tenant selection.
7. Implement: parse numeric selection against the Redis map.
8. Implement: return a Tenant detail screen for valid selection.
9. Implement: include contextual actions on the detail screen for edit and lifecycle flows.
10. Implement: handle invalid selection with a reprompt that does not lose the map.
11. Test: verify listing stores the correct map.
12. Test: verify selection loads the intended Tenant.
13. Test: verify invalid selection keeps the Master in selection flow.
14. Verify: run list/select tests and full backend suite.

## Verification

- Commands:
  - `cd backend && uv run pytest backend/tests/test_whatsapp_list_select_flow.py -v`
  - `cd backend && uv run pytest -v`
- Expected results:
  - Option `1` returns a numbered Tenant list.
  - Redis stores the displayed number-to-Tenant map.
  - Replying with a valid number opens the correct Tenant detail screen.
  - Invalid selections do not clear the flow unexpectedly.

## Exit Criteria

- The Master can list and select Tenants without typing UUIDs.
- Selected Tenant detail screen is available for later edit/lifecycle phases.
- Redis selection map behavior is covered by tests.
