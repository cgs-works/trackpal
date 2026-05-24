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