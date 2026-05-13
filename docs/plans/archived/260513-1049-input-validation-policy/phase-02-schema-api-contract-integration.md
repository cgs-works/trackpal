# Phase 2: Schema/API Contract Integration

**Complexity:** M  
**Dependencies:** Phase 1

## Objective

Apply the central policy at the Pydantic schema boundary so dashboard/API requests receive consistent `422` validation errors and accepted values are normalized before reaching services.

## Preconditions

- Phase 1 is complete and focused policy tests pass.
- Worker has inspected `backend/app/schemas/tenant.py`, `backend/app/schemas/me.py`, and `backend/app/api/v1/endpoints/tenants.py`.

## Tasks

1. Update `backend/app/schemas/tenant.py` imports to use `backend/app/core/input_validation.py` policy functions instead of direct `normalize_phone()` for tenant identity/contact fields.
2. Add a `TenantCreate.username` validator that calls `validate_username()`.
3. Add `TenantCreate.full_name` and `TenantUpdate.full_name` validators that call `validate_full_name()`.
4. Add `TenantCreate.email` and `TenantUpdate.email` validators that call `validate_email(required=False)`.
5. Add `TenantCreate.phone` and `TenantUpdate.phone` validators that call `validate_phone(required=False)`.
6. Review `ConfigDict(str_strip_whitespace=True)` in `TenantCreate`, `TenantUpdate`, and `ProfileUpdate`; adjust if needed so `full_name` leading/trailing whitespace is rejected by policy instead of silently stripped.
7. Update `backend/app/schemas/me.py` so `ProfileUpdate.full_name`, `ProfileUpdate.name` where applicable, `ProfileUpdate.email`, and `ProfileUpdate.phone` use the central policy.
8. Keep `password` validation unchanged except for import organization.
9. Ensure policy errors become clear Pydantic validation messages by converting `InputValidationError` to `ValueError` at schema validator boundaries if needed.
10. Extend `backend/tests/test_tenants.py` API tests for invalid create payloads: invalid username, invalid email, invalid phone, invalid full_name leading/trailing space, and slash command username.
11. Extend `backend/tests/test_tenants.py` API tests for normalized create payloads: email casing normalized, phone stored digits-only, full_name internal spaces collapsed.
12. Extend `backend/tests/test_profile.py` for profile update invalid email/phone/full_name and normalized accepted values.
13. Confirm endpoint conflict behavior for duplicate username/phone remains `409`, while malformed fields are `422`.

## Verification

- Commands:
  - `cd backend && uv run pytest tests/test_input_validation_policy.py -v`
  - `cd backend && uv run pytest tests/test_tenants.py -v`
  - `cd backend && uv run pytest tests/test_profile.py -v`
- Expected results:
  - Invalid API/dashboard payloads return `422` with field-specific validation details.
  - Valid payloads reach services already normalized.
  - Duplicate username/phone tests still return `409` where they did before.

## Exit Criteria

- Tenant and profile schemas reuse the central policy for all in-scope fields.
- Dashboard/API contracts reject invalid values before persistence.
- Tests demonstrate both rejection and normalized response/persistence behavior.
