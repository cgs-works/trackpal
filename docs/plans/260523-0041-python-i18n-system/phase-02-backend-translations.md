# Phase 02: Backend user-facing translations (API errors + reminders)

## Objective

- Ensure tenant/client-facing backend outputs (API errors + reminder messages) fully localized per tenant locale with English fallback.
- Implement named placeholders + locale-aware formatting in backend-generated messages.

## Scope

- Files/modules this phase may touch:
  - `backend/app/core/i18n.py` (expand catalogs + helpers)
  - `backend/app/core/errors.py` (new) or similar for `UserFacingError`
  - `backend/app/services/client_service.py`
  - `backend/app/services/catalog_service.py`
  - `backend/app/services/subscription_service.py`
  - `backend/app/services/profile_service.py`
  - `backend/app/api/v1/endpoints/clients.py`, `catalog.py`, `subscriptions.py`, `me.py`
  - `backend/app/services/subscription_job_service.py`
  - `backend/tests/test_subscriptions.py`, `backend/tests/test_clients.py`, etc.
- Files/modules this phase must not touch:
  - WhatsApp console services/facades (Phase 03)
  - Frontend (Phase 04)

## Preconditions

- Phase 01 complete: `tenants.locale` exists + `/i18n/catalog` endpoint.

## Tasks

1. Define user-facing error contract
   - Add `UserFacingError(ValueError)` with:
     - `code: str`
     - `params: dict[str, object] | None`
   - Reason: WhatsApp console currently catches `ValueError` in several flows; subclassing prevents unexpected crash before Phase 03 refactor.
   - Add helper to translate error -> message:
     - `message = t(locale, f"errors.{code}", **params)`.
   - Update API endpoints (tenant/client-visible) to catch `UserFacingError` and raise `HTTPException(status_code=409/400/etc, detail=<translated_message>)`.
     - Keep status codes same as current behavior where possible.

2. Refactor services to raise `UserFacingError` (not raw Spanish/English strings)
   - Start with `ClientService` (used heavily by tenant dashboard + tenant WhatsApp console):
     - Replace `ValueError("El nombre de usuario local ya existe")` -> `UserFacingError("client_local_username_exists")`.
     - Replace `Phone already registered` -> `UserFacingError("phone_already_registered")`.
     - Replace `Username already registered` -> `UserFacingError("username_already_registered")`.
     - Replace create/update failure generic -> `UserFacingError("client_create_failed")`, `client_update_failed`.
     - Replace delete-active -> `UserFacingError("client_delete_active")`.
   - Repeat for subscription/catalog/profile services where tenant/client sees message.
   - Update endpoints to pass/resolve locale (see task 3).

3. Locale resolution helper for endpoints
   - Add small helper (module-level function) to resolve locale for current request:
     - tenant role: load tenant by `owner_user_id` or `ActiveTenantId`.
     - client role: load tenant by `ActiveTenantId`.
   - Use this in endpoints before translating errors.
   - Keep helper in `app/api/dependencies.py` or a new `app/api/locale.py` module.

4. Expand i18n catalogs for backend errors + reminders
   - Add keys (examples):
     - `errors.phone_already_registered`
     - `errors.username_already_registered`
     - `errors.client_local_username_exists`
     - `errors.client_delete_active`
   - Add reminder templates:
     - `reminders.subscription_expiring`
       - Uses placeholders `{service_name}`, `{client_name}`, `{days}`, `{day_word}`, `{streaming_email}`.
   - Ensure Spanish missing key falls back to English.

5. Localize reminder payload generation
   - Update `SubscriptionJobService._render_reminder_message`:
     - Accept `locale` param.
     - Use `t(locale, "reminders.subscription_expiring", ...)`.
     - Determine `day_word` via translation keys or helper (en: day/days, es: día/días).
     - Use backend formatting helpers for any date/number displayed.
   - Update `generate_reminder_payloads()` to pass `tenant.locale`.

6. Tests
   - Update `backend/tests/test_subscriptions.py` reminder assertions:
     - For fixture tenant locale `es`, keep Spanish substring asserts.
     - Add new test that sets tenant.locale=`en` and asserts English reminder content.
   - Add tests for translated API errors:
     - Set tenant.locale=`en` and trigger known error, assert English detail.
     - Set tenant.locale=`es` and assert Spanish detail.
   - Add unit tests for `t()` placeholder formatting + fallback behavior + missing-key counter increments (no content leakage).

7. Backend formatting for web UI (PRD FR-15)
   - Identify date/time/number fields currently shown in tenant/client web views (eg subscriptions list uses `expires_at`).
   - Update backend responses to include locale-formatted display strings (examples):
     - `expires_at_display`, `starts_at_display`, `created_at_display`.
   - Ensure formatting uses backend locale helpers, not frontend `Intl`.
   - Update frontend in Phase 04 to use these display fields.

## Acceptance Criteria

- Tenant/client-facing API error `detail` localized by tenant locale.
- Reminder payload `message` localized by tenant locale.
- Named placeholders work; missing placeholder does not crash request (logs + safe fallback).
- Missing translation key falls back to English and emits warning + counter increment.

## Verification

- Commands:
  - `cd backend && uv run pytest -v`
- Expected results:
  - Tests asserting both `en` and `es` behavior pass.
- Evidence to record in `SUMMARY.md`:
  - Pytest summary + note of new i18n tests.

## Idempotence and Recovery

- Safe to re-run: service refactors, tests.
- Rollback notes: revert error-code conversion if needed; ensure no leaking untranslated strings.

## Exit Criteria

- [x] `UserFacingError` exists and used in tenant/client-facing services.
- [x] Endpoints translate errors using locale.
- [x] Reminder messages localized.
- [x] `uv run pytest -v` green.

