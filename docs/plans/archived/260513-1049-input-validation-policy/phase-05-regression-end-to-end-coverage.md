# Phase 5: Regression and End-to-End Coverage

**Complexity:** M  
**Dependencies:** Phase 2, Phase 3, Phase 4

## Objective

Close coverage gaps with behavior-oriented tests that prove dashboard/API, services, and WhatsApp produce the same accepted/rejected/normalized outcomes for sensitive inputs.

## Preconditions

- Phases 1-4 focused tests pass.
- Worker has reviewed current fixture behavior in `backend/tests/conftest.py` and fake services in WhatsApp tests.

## Tasks

1. Add a table-driven test section in `backend/tests/test_input_validation_policy.py` for all PRD username examples and boundary length cases: 1 char, 20 chars, and 21 chars.
2. Add API create tests in `backend/tests/test_tenants.py` comparing the same logical payload submitted with email casing and phone with/without `+`; assert persisted canonical form matches.
3. Add API update tests in `backend/tests/test_tenants.py` for invalid optional non-empty `email` and `phone` values.
4. Add profile tests in `backend/tests/test_profile.py` for Master/Tenant phone lookup and update conflicts using normalized values.
5. Add auth identify tests in `backend/tests/test_auth.py` for incoming phone with `+`, no `+`, and WhatsApp JID suffix resolving to the same canonical stored profile.
6. Extend WhatsApp create tests to run a full successful create flow with mixed-case email, phone without `+`, and full name with multiple internal spaces; assert final created fake tenant receives normalized values.
7. Extend WhatsApp create tests to assert `/menu`, `cancelar`, and `0` are not persisted as `username` when entered at username step; note global reset behavior may intercept reset commands before field validation, so assert whichever behavior is current and safe.
8. Add WhatsApp correction test: invalid email keeps email step, corrected email advances to phone, and original full_name remains in temp data.
9. Add WhatsApp duplicate username test: valid-but-existing username stays on username step and does not discard full_name/email/phone.
10. Add WhatsApp phone duplicate/service-error test if existing fake service supports it; otherwise extend fake minimally to return a phone conflict and assert flow returns to phone step.
11. Review all assertions that previously expected raw phone/email/full_name and update them to canonical expected values.
12. Run the full backend suite and fix only validation-related failures; do not broaden feature behavior.

## Verification

- Commands:
  - `cd backend && uv run pytest tests/test_input_validation_policy.py -v`
  - `cd backend && uv run pytest tests/test_auth.py tests/test_tenants.py tests/test_profile.py -v`
  - `cd backend && uv run pytest tests/test_whatsapp_create_flow.py tests/test_whatsapp_edit_flow.py tests/test_whatsapp_endpoint.py -v`
  - `cd backend && uv run pytest -v`
- Expected results:
  - All new regression tests pass.
  - Full backend suite remains green.
  - Test failures, if any, are limited to intentional changed validation expectations and are updated with clear assertions.

## Exit Criteria

- Observable behavior is covered for accepted values, rejected values, normalized values, duplicate correction, and WhatsApp step preservation.
- Dashboard/API and WhatsApp tests assert the same canonical forms for the same fields.
- The original regression class is covered by automated tests.
