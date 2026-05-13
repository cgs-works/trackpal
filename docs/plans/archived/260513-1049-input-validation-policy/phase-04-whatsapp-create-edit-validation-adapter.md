# Phase 4: WhatsApp Create/Edit Validation Adapter

**Complexity:** L  
**Dependencies:** Phase 1, Phase 3

## Objective

Reuse the central backend policy inside WhatsApp Master Console create/edit steps so invalid identity/contact values are rejected immediately, the flow stays on the correct step, and previously collected valid data is preserved.

## Preconditions

- Phase 3 service-layer enforcement passes focused tests.
- Worker has inspected `backend/app/services/whatsapp_console_service.py`, `backend/tests/test_whatsapp_create_flow.py`, and `backend/tests/test_whatsapp_edit_flow.py`.
- n8n remains transport-only; do not edit `n8n/Trackpal WhatsApp Bot.json` for business validation.

## Tasks

1. Import central policy helpers and validation error contract in `backend/app/services/whatsapp_console_service.py`.
2. Add or reuse small formatter helpers that convert field validation errors to Spanish WhatsApp replies with the relevant prompt appended.
3. In `_handle_create_full_name()`, call `validate_full_name()` before saving to `session.temp_data`; on error, return a clear message and keep `CREATE_STEP_FULL_NAME`.
4. In `_handle_create_email()`, preserve skip words for optional email; for non-skipped values call `validate_email(required=False)` and save the normalized email.
5. In `_handle_create_phone()`, preserve skip words for optional phone; for non-skipped values call `validate_phone(required=False)` and save canonical digits-only phone.
6. In `_handle_create_username()`, call `validate_username()` before duplicate checks; on invalid syntax, keep `CREATE_STEP_USERNAME` and do not call duplicate lookup.
7. Keep existing username duplicate check after normalization and keep the flow on `CREATE_STEP_USERNAME` if duplicate.
8. Ensure `_build_create_summary()` displays normalized `email`, `phone`, `username`, and `full_name` from `session.temp_data`.
9. Ensure `_handle_create_confirm()` builds payload from normalized temp data and still maps service errors back to the appropriate correction step.
10. In `_handle_edit_new_value()`, validate `full_name`, `email`, and `phone` based on `session.temp_data['edit_field']` before calling `tenant_service.update_tenant()`.
11. For edit `email` and `phone`, decide from existing behavior whether blank means invalid or clearing the optional value; implement consistently with current edit contract and document in tests.
12. Keep edit flow on `EDIT_STEP_NEW_VALUE` with selected tenant context intact when validation or service update fails.
13. Add focused WhatsApp create tests for invalid `/menu`, `0`, uppercase, spaces, and punctuation as username values.
14. Add create tests for invalid email/phone staying on the correct step and preserving `full_name` already collected.
15. Add create tests proving valid email/phone/full_name are stored normalized in session summary and create payload.
16. Add edit tests proving invalid full_name/email/phone reprompt without losing `selected_tenant_id`.
17. Avoid changing global reset command behavior outside active field validation paths.

## Verification

- Commands:
  - `cd backend && uv run pytest tests/test_whatsapp_create_flow.py -v`
  - `cd backend && uv run pytest tests/test_whatsapp_edit_flow.py -v`
  - `cd backend && uv run pytest tests/test_whatsapp_menu_flow.py tests/test_whatsapp_endpoint.py -v`
- Expected results:
  - WhatsApp create flow rejects invalid values at the field step, not only at final confirmation.
  - Invalid username examples from the PRD cannot advance to the Evolution instance step.
  - Duplicate username still keeps the username correction step.
  - Valid previous fields remain in session temp data after correcting one invalid field.
  - Existing menu/reset/help behavior remains stable.

## Exit Criteria

- WhatsApp Master Console consumes the same backend policy as API/dashboard flows.
- No field-specific regex or duplicated business rules remain in WhatsApp service for in-scope fields.
- Regression tests cover the production bug class of commands being accepted as identity data.
