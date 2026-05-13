# Phase 6: Create Tenant Flow and Regression Fix

**Complexity:** L
**Dependencies:** Phase 4

## Objective

- Implement guided Tenant creation from WhatsApp and prove the original full-name regression is fixed.

## Preconditions

- Main menu and reset behavior work.
- Redis session service can store temporary form data.
- Existing TenantService create behavior is available.

## Tasks

1. Context: inspect TenantCreate schema, TenantService create behavior, and duplicate username/phone handling.
2. Implement: route main menu option `2` to start create Tenant flow.
3. Implement: store create flow state and prompt for full name.
4. Implement: after receiving full name, store it in Redis and transition to optional email prompt.
5. Test: add regression test proving full name input continues to the email step instead of returning to main menu.
6. Implement: collect optional email with skip semantics.
7. Implement: collect optional phone with skip semantics.
8. Implement: collect username and validate duplicate username errors without resetting the flow.
9. Implement: collect Evolution Instance name with PRD-compatible optional/required behavior.
10. Implement: collect password mode: automatic or manual.
11. Implement: collect manual password only when manual mode is selected.
12. Implement: show a creation summary before creating the Tenant.
13. Implement: require textual `CONFIRMAR` before calling TenantService create.
14. Implement: on successful creation, return final result and clear Redis session.
15. Implement: handle validation errors by reprompting the current step.
16. Test: cover optional fields, duplicate username, duplicate phone, automatic password, manual password, confirmation, cancellation, and success.
17. Verify: run create flow tests and full backend suite.

## Verification

- Commands:
  - `cd backend && uv run pytest backend/tests/test_whatsapp_create_flow.py -v`
  - `cd backend && uv run pytest -v`
- Expected results:
  - Starting create flow prompts for full name.
  - Sending full name transitions to email prompt and does not return main menu.
  - Optional email/phone can be skipped.
  - Duplicate username/phone errors keep the user on the relevant step.
  - Tenant is created only after `CONFIRMAR`.
  - Session clears after successful creation or explicit cancellation.

## Exit Criteria

- Full create Tenant flow works from WhatsApp behavior perspective.
- Original full-name regression is covered and passing.
- Creation uses existing Tenant lifecycle rules.
- No real WhatsApp messages are sent in tests.
