# Error Handling

> Error contract and propagation rules.

## Overview

- Domain/user-facing validation conflicts use `UserFacingError` (`app/core/errors.py`).
- Endpoints translate `UserFacingError` via `translate_error(locale, exc)`.
- Preserve HTTP semantics (`400`, `401`, `403`, `404`, `409`) by endpoint context.

## Error Types

- `UserFacingError(code, params)` for translatable business errors.
- `HTTPException` at API boundary only.
- Raw exceptions only for unexpected/internal failures.

## Handling Pattern

1. Endpoint resolves locale early when needed.
2. Call service.
3. Catch `UserFacingError` first, map to localized `HTTPException`.
4. Catch `ValueError` legacy paths second.

Examples:
- `backend/app/api/v1/endpoints/clients.py`
- `backend/app/api/v1/endpoints/catalog.py`
- `backend/app/api/v1/endpoints/tenants.py`

## API Error Responses

- Use FastAPI `HTTPException(detail=<string>)`.
- Keep detail user-facing for expected errors.
- Keep auth/API-key errors explicit (`Invalid API Key`, auth invalid/expired).

## Common Mistakes

- Catching `ValueError` before `UserFacingError`.
- Translating without locale resolution.
- Raising HTTPException inside repository layer.
- Returning mixed-language hardcoded strings in services.

## Gotchas: External API Error Misdiagnosis

### Symptom
HTTP 403 from external Evolution API with message `"This name \"undefined\" is already in use."`

### Cause
Body fields arriving as literal `"undefined"` → server can't parse JSON body correctly. Usually means **server version mismatch**: code was written for API version X but deployed server runs version Y.

### Diagnosis
Check server identity before diving into code:
```bash
# Check server version and framework
curl -s "$BASE_URL/"
# → {"version":"2.4.0", ...}  # Evolution API (Node/Express)
# Headers: X-Powered-By: Express → NOT Go version

# Then test raw endpoint
curl -v -X POST "$BASE_URL/instance/create" \
  -H "Content-Type: application/json" \
  -H "apikey: $KEY" \
  -d '{"name":"test","token":"test123"}'
```

### Fix
1. Verify deployed server version (root `/` gives version + framework)
2. If server is old version, update it or adapt payload to match
3. If body format correct but 403 persists, check `apikey` header matches server `GLOBAL_API_KEY`

### Prevention
- Before writing integration code, probe deployed server to confirm version/framework
- Add a startup check or connectivity test that verifies the expected API contract
- Treat 403 with body-parsing errors as "server version mismatch" until proven otherwise