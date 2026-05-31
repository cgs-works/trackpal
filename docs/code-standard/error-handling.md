# Error Handling Conventions

Error contract and propagation rules used across the backend.

## Error Types

| Type | Where | Purpose |
|------|-------|---------|
| `UserFacingError(code, params)` | `app/core/errors.py` | Translatable business errors raised in services |
| `HTTPException(status_code, detail)` | API endpoints | API boundary error responses |
| Raw exceptions | Services only | Unexpected/internal failures, caught and mapped in endpoints |

## Propagation Pattern

1. Endpoint resolves locale early via `resolve_locale(db, tenant_id)`.
2. Endpoint calls service.
3. Service raises `UserFacingError` for domain/user-facing validation conflicts.
4. Endpoint catches `UserFacingError` **first**, translates via `translate_error(locale, exc)`.
5. Endpoint catches `ValueError` legacy paths **second** (after `UserFacingError`).

## Sequence

```python
# Correct order
try:
    result = await some_service.do_thing(db, data)
except UserFacingError as exc:
    raise translate_error(locale, exc)
except ValueError as exc:
    raise HTTPException(status_code=400, detail=str(exc))
```

## API Error Responses

- Use FastAPI `HTTPException(detail=<string>)`.
- Detail is user-facing for expected errors.
- Auth/API-key errors use explicit messages (`"Invalid API Key"`, auth invalid/expired).

## Common Mistakes

- Catching `ValueError` before `UserFacingError` — bypasses i18n translation.
- Translating without locale resolution — returns wrong language or crashes on post-rollback DB read.
- Raising `HTTPException` inside repository layer — breaks layering; repositories know nothing about HTTP.
- Returning mixed-language hardcoded strings in services.

## Locale Resolution Timing

`resolve_locale()` from `app/api/dependencies.py` must be called **before** mutating service calls. After a failed transaction, post-rollback RLS context may prevent reading tenant row.

## External API Error Misdiagnosis

HTTP 403 from Evolution API with `"This name 'undefined'"` likely means **server version mismatch**: code written for API version X but deployed server runs version Y.

Diagnosis:
```bash
# Check server version and framework
curl -s "$BASE_URL/"
# → {"version":"2.4.0"} + headers X-Powered-By: Express  (Node/Express)
# vs headers without Express (Go/Gin)
```

Fix: probe deployed server before integration coding. See [Evolution Integration](../architecture/evolution-integration.md).

## Related

- [Backend Conventions](backend-conventions.md)
- [Logging Guidelines](logging-guidelines.md)
- [API Layer](../architecture/api-layer.md)
