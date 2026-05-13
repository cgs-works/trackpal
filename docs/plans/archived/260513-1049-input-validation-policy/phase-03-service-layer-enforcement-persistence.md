# Phase 3: Service-Layer Enforcement and Persistence Invariants

**Complexity:** M  
**Dependencies:** Phase 1, Phase 2

## Objective

Add service-layer validation as a defensive safety net so direct service calls, test doubles, seeds, profile paths, and future adapters cannot bypass the backend policy before persistence or duplicate checks.

## Preconditions

- Phase 2 schema/API tests pass.
- Worker has inspected `backend/app/services/tenant_service.py`, `backend/app/services/profile_service.py`, `backend/app/crud/users.py`, `backend/scripts/seed.py`, and current tests/fixtures.

## Tasks

1. In `backend/app/services/tenant_service.py`, validate/normalize `payload.username`, `payload.full_name`, `payload.email`, and `payload.phone` at the start of `create_tenant()` before duplicate checks.
2. Use normalized `username` for `user_crud.get_by_username()` and `User(username=...)`.
3. Use normalized `phone` for `user_crud.get_by_phone()` and `TenantProfile(phone=...)`.
4. Use normalized `full_name` and `email` when creating `TenantProfile`.
5. In `TenantService.update_tenant()`, normalize any provided `full_name`, `email`, and `phone` before duplicate checks and assignment.
6. Ensure updating `phone` to `None` remains allowed only where the schema/service currently allows optional phone.
7. In `backend/app/services/profile_service.py`, validate/normalize update fields before conflict checks and assignment for Master/Tenant profile updates.
8. In `backend/app/crud/users.py`, keep or add defensive normalization for phone lookup so lookup inputs with `+` or WhatsApp suffixes still resolve to canonical stored digits.
9. In `backend/app/services/auth_service.py`, ensure identify-by-phone uses the same canonical phone lookup path and remains compatible with ADR-0004.
10. In `backend/scripts/seed.py`, validate/normalize seeded Master username/name/phone as applicable without changing unrelated seed behavior.
11. Add or update service-level tests that construct schema-like objects or direct payloads and verify normalized persisted values.
12. Add tests proving invalid values rejected at service layer raise `ValueError`/project-consistent errors even if schema validation is bypassed.
13. Review error messages in service exceptions so API and WhatsApp adapters can map `username`, `phone`, `email`, and `full_name` failures to the correct field.

## Verification

- Commands:
  - `cd backend && uv run pytest tests/test_auth.py -v`
  - `cd backend && uv run pytest tests/test_tenants.py -v`
  - `cd backend && uv run pytest tests/test_profile.py -v`
  - `cd backend && uv run pytest tests/test_phone_normalizer.py tests/test_input_validation_policy.py -v`
- Expected results:
  - Direct and schema-mediated Tenant/Profile operations persist canonical values.
  - Phone identity lookup still works for `+` and JID-style inputs.
  - Duplicate checks operate on normalized values.
  - Existing auth/profile/tenant behavior remains unchanged outside validation errors.

## Exit Criteria

- No Tenant/Profile persistence path can store invalid in-scope identity/contact values through normal backend services.
- Duplicate username and phone checks run after normalization.
- Seed and identify paths remain compatible with canonical phone storage.
