# Phase 1: Dependencies and Central Validation Policy

**Complexity:** M  
**Dependencies:** None

## Objective

Install the required validation libraries and introduce a single backend policy module that validates and normalizes `username`, `email`, `phone`, and `full_name` without touching API/service/WhatsApp callers yet.

## Preconditions

- Existing backend tests pass before starting.
- Worker has read `docs/prds/260513-1049-input-validation-policy/PRD.md`, `CONTEXT.md`, ADR-0003, and ADR-0004.

## Tasks

1. Add `email-validator` and `phonenumbers` dependencies using `cd backend && uv add email-validator phonenumbers` so both `pyproject.toml` and `uv.lock` update.
2. Create `backend/app/core/input_validation.py`.
3. Define a small exception/result contract for field validation errors, e.g. `InputValidationError(field: str, message: str, code: str)` plus functions that return normalized values or raise this error.
4. Implement `validate_username(value: str) -> str` with rules: required non-empty string, max 20 chars, starts with lowercase ASCII letter, remaining chars only lowercase ASCII letters, digits, and `_`.
5. Implement `validate_full_name(value: str) -> str` with rules: required non-empty string, reject leading/trailing whitespace, allow letters, numbers, and spaces, collapse multiple internal spaces to one in the returned value.
6. Implement `validate_email(value: str | None, *, required: bool = False) -> str | None` using `email_validator.validate_email(..., check_deliverability=False)` and return the library-normalized email; allow `None` only when not required.
7. Implement `validate_phone(value: str | None, *, required: bool = False) -> str | None` using `phonenumbers`; accept E.164-style input with optional leading `+`; return `PhoneNumberFormat.E164` stripped to digits only; allow `None` only when not required.
8. Preserve WhatsApp JID cleanup behavior needed by existing phone flows by routing `backend/app/core/phone.py::normalize_phone()` through a helper that strips JID/device suffixes before validation/normalization where appropriate.
9. Add `backend/tests/test_input_validation_policy.py` with valid examples for each field.
10. Add username invalid tests for `/menu`, `hola mundo`, `Admin!`, `Ñandu`, `0admin`, `_admin`, blank, and length > 20.
11. Add full-name tests for valid letters/numbers/spaces, internal multi-space collapse, leading/trailing space rejection, slash/punctuation rejection, and blank rejection.
12. Add email tests for normalized casing, invalid syntax, blank/optional handling, and no deliverability dependency.
13. Add phone tests for `+14155552671`, `14155552671`, invalid short/ambiguous values, non-phone text, blank optional handling, and canonical digits-only output.
14. Run formatting/lint style consistent with existing project conventions; do not introduce a new lint tool.

## Verification

- Commands:
  - `cd backend && uv sync`
  - `cd backend && uv run pytest tests/test_input_validation_policy.py -v`
  - `cd backend && uv run pytest tests/test_phone_normalizer.py -v`
- Expected results:
  - New policy tests pass.
  - Existing phone normalizer tests continue to pass or are deliberately updated only for stricter persistence-validation semantics while preserving JID cleanup utility behavior.
  - `backend/pyproject.toml` and `backend/uv.lock` contain both new dependencies.

## Exit Criteria

- `backend/app/core/input_validation.py` is the sole owner of the new field rules.
- Isolated tests prove valid, invalid, boundary, and normalization behavior for all four fields.
- Existing phone utility remains compatible for current identity/session cleanup callers.
