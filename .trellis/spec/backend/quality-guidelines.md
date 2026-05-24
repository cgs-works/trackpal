# Quality Guidelines

> Backend quality gates used in Trackpal.

## Required Patterns

- Async FastAPI handlers and SQLAlchemy async sessions.
- Thin endpoint handlers, business logic in services.
- Reusable query logic in repositories.
- Shared input normalization via `app/core/input_validation/*`.
- i18n-aware user errors via `UserFacingError` + endpoint translation.

## Forbidden Patterns

- New monolith files >240 LoC (target <=200).
- SQL in API endpoints unless urgent temporary hotfix.
- Hardcoded frontend-visible translation strings in services.
- Committing debug prints/temp code.

## Scenario: WhatsApp tenant subscriptions prompts must use i18n keys

### 1. Scope / Trigger
- Trigger: tenant console subscriptions edit prompts were hardcoded in Spanish inside service constants.

### 2. Signatures
- Constants contract:
  - `SUBSCRIPTIONS_EDIT_PROMPT_KEYS: dict[str, str]` (field -> i18n key)
- Runtime contract:
  - `self._t(key: str, **kwargs) -> str` resolves locale-aware message.

### 3. Contracts
- `subscription_constants.py` must expose keys, not localized message bodies.
- `subscriptions_edit.py` must call `_t(...)` for prompt rendering.
- WA catalogs must contain matching keys in both ES and EN.

### 4. Validation & Error Matrix
- Unknown edit field -> `KEY_SUBSCRIPTIONS_EDIT_ERROR_INVALID_FIELD`.
- Missing i18n key -> engine fallback warning + non-crash response.

### 5. Good/Base/Bad Cases
- Good: map `"streaming_email" -> "wa.tenant.subscriptions.edit.streaming_email_prompt"` then `_t(...)`.
- Base: keep field routing map (`1..7`) unchanged.
- Bad: inline `"✏️ *Editar Suscripción* ..."` in constants.

### 6. Tests Required
- Focused backend tests:
  - tenant console edit flow + subscriptions flow tests.
  - assert responses vary by locale/catalog and include expected key content.
- Regression: run WhatsApp tenant console subset.

### 7. Wrong vs Correct
#### Wrong
```python
SUBSCRIPTIONS_EDIT_PROMPTS = {"streaming_email": "✏️ *Editar Suscripción* ..."}
```
#### Correct
```python
SUBSCRIPTIONS_EDIT_PROMPT_KEYS = {
    "streaming_email": "wa.tenant.subscriptions.edit.streaming_email_prompt",
}
prompt = self._t(SUBSCRIPTIONS_EDIT_PROMPT_KEYS[field])
```

## Testing Requirements

- Run backend suite before completion: `cd backend && uv run pytest -v`.
- For scoped edits run focused tests first, then full suite.
- Keep async test patterns from `backend/tests/conftest.py` fixtures.

## Review Checklist

- Layering respected (`api -> services -> repositories`).
- Endpoint status codes unchanged unless intentional.
- Imports stable through package `__init__.py` re-exports.
- No secrets in logs/errors.
- LoC policy respected; debt explicitly documented for 201-240 range.

## Evidence examples

- Full-suite baseline used in refactor: `781 passed, 1 skipped`.
- Endpoint package modularization: `backend/app/api/v1/endpoints/subscriptions/*`.
- Repository migration examples: `backend/app/repositories/*`.