# Type Safety

> Type safety reality in current frontend.

## Overview

- Frontend is JavaScript-only (no TypeScript).
- Runtime validation and backend contracts are primary safety mechanisms.

## Type Organization

- No dedicated type files today.
- Contract shapes inferred from backend schemas/endpoints and usage in views/stores.

## Validation

- Backend enforces strict schema validation (FastAPI + Pydantic).
- Frontend validates user flows with guard clauses and API error handling.
- i18n catalogs fetched from backend (`/api/v1/i18n/catalog`) reduce string-shape drift.

## Common Patterns

- Defensive optional chaining on API errors:
  - `error.response?.data?.detail`
- Array detail normalization pattern from frontend conventions doc.

## Forbidden Patterns

- Pretending TS types exist.
- Silent `catch {}` without user feedback.
- Hardcoded translation dictionaries in frontend source.

## Migration note

If TypeScript is adopted later, add explicit `types/` and update this spec. For now document JS reality, not aspirational TS rules.