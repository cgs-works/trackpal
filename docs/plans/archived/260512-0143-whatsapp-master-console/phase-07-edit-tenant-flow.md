# Phase 7: Edit Tenant Flow

**Complexity:** M
**Dependencies:** Phase 5

## Objective

- Allow the Master to edit selected Tenant fields from the WhatsApp Tenant detail screen.

## Preconditions

- Tenant list/select/detail flow works.
- Selected Tenant identity can be stored in Redis.
- Existing TenantService update behavior is available.

## Tasks

1. Context: inspect Tenant update schema and validation behavior.
2. Implement: add edit actions to the selected Tenant detail screen.
3. Implement: route edit full name action to await a new full name.
4. Implement: route edit email action to await a new email.
5. Implement: route edit phone action to await a new phone.
6. Implement: route edit Evolution Instance action to await a new Evolution Instance name.
7. Implement: store selected field and selected Tenant in Redis while awaiting the new value.
8. Implement: call TenantService update after receiving a valid new value.
9. Implement: return the updated Tenant detail screen after successful edit.
10. Implement: handle validation errors without clearing selected Tenant context.
11. Test: cover valid updates for each editable field.
12. Test: cover invalid email/phone and duplicate phone behavior.
13. Test: cover cancel/reset from an edit step.
14. Verify: run edit flow tests and full backend suite.

## Verification

- Commands:
  - `cd backend && uv run pytest backend/tests/test_whatsapp_edit_flow.py -v`
  - `cd backend && uv run pytest -v`
- Expected results:
  - Master can edit full name, email, phone, and Evolution Instance from the detail screen.
  - Valid edits persist and return updated detail.
  - Invalid edits reprompt without losing selected Tenant context.
  - Reset commands clear the edit flow.

## Exit Criteria

- Tenant edit flow works for all PRD fields.
- Backend validation behavior is preserved.
- Tests cover valid, invalid, and cancellation paths.
