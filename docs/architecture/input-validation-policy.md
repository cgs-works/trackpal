# Input Validation Policy

Centralized input validation lives in `app/core/input_validation.py` and is the single source of truth for all field validation and normalization rules.

## Design

- All validators return normalized values on success
- All validators raise `InputValidationError(field, message, code)` on failure
- Used by both Pydantic API schemas (via `@field_validator`) and WhatsApp console flow (`_validation_error_reply`)
- Spanish error messages are mapped from error codes in `WhatsAppConsoleService._VALIDATION_MESSAGES`

## Validators

### `validate_username(value: str) → str`

| Rule | Detail |
|------|--------|
| Required | Non-empty after strip |
| Max length | 20 characters |
| Start | Must be lowercase ASCII letter (a-z) |
| Content | Lowercase letters, digits, underscores only |
| Whitespace | No leading or trailing spaces |

### `validate_full_name(value: str) → str`

| Rule | Detail |
|------|--------|
| Required | Non-empty after strip |
| Allowed chars | Unicode letters, digits, spaces only |
| Punctuation | Rejected |
| Normalization | Collapses multiple internal spaces to one |
| Whitespace | No leading or trailing spaces |

### `validate_email(value: str | None, *, required=False) → str | None`

- Uses `email_validator` library with `check_deliverability=False`
- Returns normalized email or None for optional empty input
- No DNS/MX/SMTP checks

### `validate_phone(value: str | None, *, required=False) → str | None`

- Uses `phonenumbers` library for E.164 validation
- Accepts input with or without leading `+`
- Returns canonical digits-only form (no `+` prefix)
- Strips WhatsApp JID suffixes (`@c.us`, `@s.whatsapp.net`) and device suffixes (`:N`)
- Rejects extension patterns (ext, x, #) and invalid characters

## Phone Normalizer (`app/core/phone.py`)

`normalize_phone(value: str | None) → str | None`:
- Removes `+` prefix, JID suffixes, device suffixes
- Strips all non-digit characters
- Returns `None` for blank/no-digit input
- Used by CRUD, auth, and integrations for phone lookup

## Schema Integration

Pydantic schemas in `app/schemas/tenant.py`, `app/schemas/me.py` use `@field_validator` decorators that call input validation functions. The service layer also applies defensive normalization as a safety net.
