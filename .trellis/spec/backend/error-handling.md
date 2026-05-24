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