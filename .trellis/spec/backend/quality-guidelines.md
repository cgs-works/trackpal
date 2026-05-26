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

## Scenario: WhatsApp tenant subscriptions filtered list must be interactive and paginated

### 1. Scope / Trigger
- Trigger: filtered subscriptions list mixed hardcoded Spanish labels and inconsistent navigation (`0` missing in some views, no stable pagination commands).

### 2. Signatures
- Formatter signature:
  - `_format_subscription_list(..., page: int = 1, total_pages: int = 1) -> str`
- Flow handlers:
  - `_handle_subscriptions_filter(...)` initializes paginated list context.
  - `_handle_subscriptions_list(...)` routes `8/9` navigation and `1..7` selection.

### 3. Contracts
- Session temp contract:
  - `temp_data['status']`: selected filter status
  - `temp_data['page']`: current page (1-based)
- Selection map contract:
  - Rebuilt per page with keys `"1".."7"` only.
- Command contract in list step:
  - `0` cancel/exit (global reset path)
  - `8` previous page (if `page > 1`)
  - `9` next page (if `page < total_pages`)
- WA i18n keys required in ES/EN catalogs:
  - list header, status labels, detail labels, page navigation labels.

### 4. Validation & Error Matrix
- `8` on first page -> localized invalid option/keep page.
- `9` on last page -> localized invalid option/keep page.
- Selection outside `1..7` current map -> localized invalid option.
- Missing i18n key -> fallback warning; response must not crash.

### 5. Good/Base/Bad Cases
- Good: list with >7 records shows 7 items + `8`/`9` nav + `0` cancel.
- Base: list with <=7 records shows only `1..N` + `0` cancel.
- Bad: rendering all subscriptions in one page or mapping `8/9` to subscription IDs.

### 6. Tests Required
- Focused backend tests:
  - tenant console subscriptions list flow with >7 records.
  - assert page transitions on `8`/`9`.
  - assert `selection_map` keys limited to `1..7` each page.
  - assert `0` appears in rendered list and still exits flow.
- Regression command:
  - `cd backend && uv run pytest tests/test_tenant_console_service.py -v -k "subscriptions"`

### 7. Wrong vs Correct
#### Wrong
```python
for i, subscription in enumerate(all_subscriptions, 1):
    options.append(f"{i}️⃣ ...")
# No explicit 0, no page navigation
```
#### Correct
```python
visible = filtered[(page-1)*7 : page*7]
session.selection_map = {str(i): sub.id for i, sub in enumerate(visible, 1)}
# 8 prev if page>1, 9 next if page<total_pages, 0 cancel always
```

## Scenario: External API integration contract must be verified against deployed server

### 1. Scope / Trigger
- Trigger: Integration code written for Evolution Go (Go/Gin) while deployed server was Evolution API v2.4.0 (Node/Express). Result: 403 "This name 'undefined'" because Express didn't parse body the same way.

### 2. Signatures
- Server probe: `GET $BASE_URL/` returns `{"version":"2.4.0", ..., "manager":"..."}` + headers reveal framework (`X-Powered-By: Express` vs Gin)
- Direct test: `curl -v $BASE_URL/instance/create` with exact payload proves whether contract is correct

### 3. Contracts
- Before coding against any external API endpoint, verify:
  1. Deployed server version via root `/` endpoint
  2. Actual response headers (framework signature)
  3. Raw curl test of target endpoint with example payload
  4. Response shape matches documented contract
- If docs live in a local repo, they may describe a different version than deployed

### 4. Validation & Error Matrix
- 403 + "name 'undefined'" + `X-Powered-By: Express` → server is Node/Express, not Go/Gin
- 401/403 with no body → `apikey` header mismatch
- 200 with unexpected response shape → docs contract != deployed contract

### 5. Good/Base/Bad Cases
- Good: Probe server first, confirm version matches expected contract, then write integration
- Base: Write code against local docs, test against deployed, debug mismatch
- Bad: Write code against local docs, ship, discover mismatch only after deployment

### 6. Tests Required
- Integration test should probe `GET $BASE_URL/` and assert `version` in response as a connectivity check
- Mock-based unit tests must not silently pass when real contract differs

### 7. Wrong vs Correct
#### Wrong (blind trust)
```python
# Code written against local evolution-go repo docs
# but deployed server is evolution-api v2.4.0 (Express)
payload = {"name": name, "token": token}
response = await client.post("/instance/create", json=payload)
# → 403 "This name 'undefined'", server didn't parse correctly
```
#### Correct (probe first)
```python
# Probe server first
root = await client.get("/")
version = root.json().get("version")

# If version != expected, stop or adapt
if version != config.expected_evolution_version:
    logger.warning(f"Server version {version} != expected {config.expected_evolution_version}")

# Test raw endpoint before integrating
probe = await client.post("/instance/create", json={"name": "ping", "token": "ping"})
assert probe.status_code != 403, f"Body parsing failed for /instance/create"
```

## Testing Requirements

- Run backend suite before completion: `cd backend && uv run pytest -v`.
- For scoped edits run focused tests first, then full suite.
- Keep async test patterns from `backend/tests/conftest.py` fixtures.
- Always probe external API endpoints directly with curl before assuming contract from docs.

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