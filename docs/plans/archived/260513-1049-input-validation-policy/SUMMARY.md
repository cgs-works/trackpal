# Implementation Plan: Centralized Input Validation Policy

## Objective

- Add a backend-owned, centralized input validation policy for sensitive identity/contact fields: `username`, `email`, `phone`, and `full_name`.
- Use `email-validator` for email syntax validation and normalization without deliverability/DNS checks.
- Use `phonenumbers` for phone validation against E.164-interpretable input with optional `+`, storing canonical digits-only values.
- Enforce strict positive rules for usernames and full names consistently across dashboard/API schemas, service persistence, profile updates, seed-compatible paths, and WhatsApp Master Console flows.
- Add regression coverage for the production bug where WhatsApp accepted commands or invalid text as identity data.
- Link to PRD: `docs/prds/260513-1049-input-validation-policy/PRD.md`

## Scope

### In scope

- Backend validation policy module with reusable functions/classes for `username`, `email`, `phone`, and `full_name`.
- Dependency updates in `backend/pyproject.toml` and `backend/uv.lock` for `email-validator` and `phonenumbers`.
- Pydantic V2 schema integration for Tenant create/update and profile update payloads.
- Service-layer defensive enforcement before Tenant/Profile persistence and phone/username duplicate checks.
- WhatsApp Master Console step-level validation and clear reprompts for invalid `full_name`, `email`, `phone`, and `username` without losing prior collected data.
- Consistent persisted canonical forms:
  - `username`: unchanged valid lowercase identifier.
  - `email`: normalized output from `email-validator`.
  - `phone`: digits only, no `+`.
  - `full_name`: internal multiple spaces collapsed to one.
- Regression tests for dashboard/API contracts, service invariants, WhatsApp create/edit flows, and canonicalized persistence.
- Minimal documentation/context updates only where needed to reflect the new backend policy module.

### Out of scope

- Email deliverability, DNS, MX, or SMTP checks per request.
- Country-specific phone heuristics or accepting local/national formats that are not interpretable as E.164.
- Frontend reimplementation of rich validation rules; backend remains source of truth.
- n8n workflow business-rule changes; n8n remains transport-only per ADR-0003.
- Broad UX copy refactors unrelated to these field validation errors.
- Database type changes or new entities.

## Architecture & Approach

- Create a small backend policy module, recommended target `backend/app/core/input_validation.py`, that owns all field rules and returns normalized values or field-specific validation errors.
- Keep existing `backend/app/core/phone.py` as the compatibility entry point for current callers, but route its behavior through the new phone policy or update it to use the same implementation so there is one source of truth.
- Integrate policy into Pydantic schemas for early API/dashboard validation. Pydantic validation errors should naturally produce HTTP `422` for malformed request fields.
- Keep service-layer enforcement in `TenantService` and `ProfileService` as a safety net so direct service calls and WhatsApp adapters cannot bypass invariants.
- In WhatsApp, validate each field at the step where it is entered, store normalized values in `session.temp_data`, keep the current step on errors, and preserve previously collected valid fields.
- Avoid command blacklists as the main defense. `/menu`, `0`, `cancelar`, spaces, uppercase, punctuation, and non-ASCII username examples must be rejected by positive field rules.
- Preserve existing duplicate-check behavior for username/phone, but ensure duplicate checks use normalized values.

## Phases

- [ ] **Phase 1 [M]: Dependencies and central validation policy** — Add libraries, define reusable policy API, and cover field rules with isolated unit tests.
- [ ] **Phase 2 [M]: Schema/API contract integration** — Apply the policy to Tenant/Profile schemas so dashboard/API requests reject or normalize fields consistently.
- [ ] **Phase 3 [M]: Service-layer enforcement and persistence invariants** — Add defensive normalization/validation before persistence and duplicate checks, including seed/profile paths.
- [ ] **Phase 4 [L]: WhatsApp create/edit validation adapter** — Reuse the central policy in WhatsApp steps, reprompt on invalid inputs, preserve state, and normalize temp data before confirmation.
- [ ] **Phase 5 [M]: Regression and end-to-end coverage** — Add focused tests for API, services, persisted canonical forms, WhatsApp regressions, and duplicate-correction flows.
- [ ] **Phase 6 [S]: Documentation and full verification** — Update minimal docs/context and run the complete backend verification suite.

## Key File Targets

- `backend/pyproject.toml` and `backend/uv.lock` — add `email-validator` and `phonenumbers`.
- `backend/app/core/input_validation.py` — new central policy module.
- `backend/app/core/phone.py` — keep compatibility wrapper aligned with phone policy.
- `backend/app/schemas/tenant.py` — validators for create/update payloads.
- `backend/app/schemas/me.py` — validators for profile updates.
- `backend/app/services/tenant_service.py` — defensive enforcement and normalized duplicate checks.
- `backend/app/services/profile_service.py` — defensive enforcement for profile edits.
- `backend/scripts/seed.py` — seed-compatible validation/normalization of Master identity/contact values where applicable.
- `backend/app/services/whatsapp_console_service.py` — field-step validation, error messages, state preservation.
- `backend/tests/test_input_validation_policy.py` — new isolated policy tests.
- `backend/tests/test_tenants.py`, `backend/tests/test_profile.py`, `backend/tests/test_auth.py` — contract/service regression coverage.
- `backend/tests/test_whatsapp_create_flow.py`, `backend/tests/test_whatsapp_edit_flow.py`, `backend/tests/test_whatsapp_endpoint.py` — WhatsApp regression coverage.
- `CONTEXT.md`, `CONTEXT-MAP.md`, and optionally `docs/codebase/backend.md` — minimal map updates after implementation.

## Verification Strategy

Run focused tests after each phase. Run the full backend test suite after shared policy, service, or WhatsApp behavior changes.

Core commands:

- `cd backend && uv sync`
- `cd backend && uv run pytest tests/test_input_validation_policy.py -v`
- `cd backend && uv run pytest tests/test_tenants.py tests/test_profile.py tests/test_auth.py -v`
- `cd backend && uv run pytest tests/test_whatsapp_create_flow.py tests/test_whatsapp_edit_flow.py tests/test_whatsapp_endpoint.py -v`
- `cd backend && uv run pytest -v`

## Dependencies

- Existing FastAPI/Pydantic V2 validation layer.
- Existing `normalize_phone()` callers and phone canonicalization expectations from ADR-0004.
- Existing backend-owned WhatsApp console and Redis session flow from ADR-0003 and ADR-0004.
- `email-validator` package for email normalization with `check_deliverability=False`.
- `phonenumbers` package for E.164 parsing/validation.
- Existing pytest async patterns and fake tenant/session services.

## Risks & Mitigations

- **Phone policy may conflict with existing permissive digit-stripping normalizer** → add focused tests for old WhatsApp JID cleanup plus new E.164 validity; keep a compatibility wrapper but centralize validation for persistence.
- **Pydantic `str_strip_whitespace=True` can hide full-name leading/trailing space errors** → explicitly inspect raw values in field validators or remove model-level stripping for fields where leading/trailing spaces must be rejected before normalization.
- **Email normalization may reject existing test fixture emails** → use realistic valid domains in tests and disable deliverability checks.
- **WhatsApp duplicate or persistence errors could return user to the wrong step** → test username and phone duplicate failures keep the correction step and preserve previous valid fields.
- **Service calls in tests may bypass Pydantic schemas** → enforce policy again in services and add direct service tests.
- **Over-expanding validation scope** → limit implementation to fields named in the PRD and existing Tenant/Master/Profile/WhatsApp paths.

## Open Questions / Assumptions

- Full-name leading/trailing spaces are treated as validation errors, while multiple internal spaces are normalized by collapsing to one before storage.
- Email and phone remain optional only where current contracts allow `None`/skip; invalid non-empty values are rejected.
- `phone` input must represent an international E.164 number with country code; optional `+` is added only for parsing if omitted.
- Existing database rows are assumed already mostly canonical from prior phone normalization work; this plan does not include a DB migration unless implementation discovers non-canonical persisted values that tests or local data require addressing.

## Handoff

Plan artifacts are ready under `docs/plans/260513-1049-input-validation-policy/`.
