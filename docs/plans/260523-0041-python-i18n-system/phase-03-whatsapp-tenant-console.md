# Phase 03: Tenant WhatsApp console localization + locale switch flow

## Objective

- Localize all tenant WhatsApp console prompts/menus/validation/errors to tenant locale (`en`/`es`) with English fallback.
- Add locale change flow inside tenant WhatsApp profile/settings; apply immediately in same active session.
- Ensure translation lookup happens at runtime per message, not at import/class definition.

## Scope

- Files/modules this phase may touch:
  - `backend/app/services/whatsapp_tenant_console_service.py`
  - `backend/app/services/whatsapp_tenant_console_facade.py`
  - `backend/app/api/v1/endpoints/integrations.py` (tenant console path)
  - `backend/app/services/auth_service.py` (optional: enrich identity with tenant locale)
  - `backend/app/core/i18n.py` (add WhatsApp keys)
  - `backend/tests/test_tenant_console_service.py`
- Files/modules this phase must not touch:
  - Master WhatsApp console (`whatsapp_console_service.py`, `whatsapp_master_console_facade.py`) except shared policy strings if strictly required.
  - Frontend (Phase 04)

## Preconditions

- Phase 01 complete: tenant locale persisted + updatable.
- Phase 02 complete: i18n catalogs expanded + `t()` stable.

## Tasks

1. Decide locale resolution point for WhatsApp tenant console
   - Recommended: resolve locale per message from DB (ensures immediate effect after change).
   - Implementation options:
     - (A) In `WhatsAppTenantConsoleFacade.process_message()`: after tenant lookup, read `tenant.locale` and pass into console service.
     - (B) In `AuthService.identify_by_phone()`: include `tenant_id` + `tenant_locale` in returned identity dict; avoid duplicate queries.
   - Ensure no caching of locale in Redis session beyond convenience (must re-check each message).

2. Refactor reply templates to runtime i18n lookups
   - In `WhatsAppTenantConsoleService`:
     - Replace class constants containing Spanish strings with either:
       - key constants (eg `KEY_MAIN_MENU = "wa.tenant.main_menu"`), or
       - inline calls `t(locale, "wa.tenant.main_menu")` at return sites.
     - Add helper method `_t(locale, key, **params)` for brevity.
     - Avoid calling `t()` at class definition time.
   - Concurrency safety:
     - `WhatsAppTenantConsoleService` instantiated once in `integrations.py`; do not store locale on service instance.
     - Either pass locale explicitly through handlers, or use `contextvars.ContextVar` set/reset per message.
   - Cover:
     - MAIN_MENU, HELP_TEXT, fallbacks
     - All client flows prompts + confirmations
     - Catalog prompts
     - Profile prompts + password change
     - Subscriptions prompts + confirmations

3. Localize facade-level replies
   - In `whatsapp_tenant_console_facade.py`, translate:
     - `INACTIVE_TENANT_REPLY`, `TENANT_NOT_FOUND_REPLY`, `GOODBYE_REPLY`.
   - For non-tenant callers (role mismatch), keep Spanish (master fixed Spanish) or default English (documented); choose once and keep consistent.

4. Add WhatsApp locale change flow
   - Update PROFILE menu:
     - Add option: `Cambiar idioma / Change language`.
   - Add new steps:
     - `PROFILE_STEP_CHANGE_LOCALE_SELECT`.
   - Prompts:
     - Show current locale and options:
       - `1) English`, `2) Español`, `0) Back`.
   - On selection:
     - Call `ProfileService.update_profile(..., ProfileUpdate(locale=<...>))`.
     - Confirm in new locale.
     - Next reply in same session must use updated locale (requires per-message locale resolution).

5. Update tests
   - Update `backend/tests/test_tenant_console_service.py`:
     - Stop importing raw reply constants if they become keys.
     - Assert localized output for tenant locale `es` and `en`:
       - Set tenant.locale in DB fixture before calling facade.
       - Verify main menu contains expected language.
     - Add test for immediate locale switch:
       - Start profile flow -> change locale -> next reply in new language without new session.

## Acceptance Criteria

- Tenant WhatsApp console replies fully localized per tenant locale.
- Locale change inside WhatsApp console applies immediately to next reply in same session.
- No translation lookup executed at import/class-definition time (review code for `t()` calls in constants).

## Verification

- Commands:
  - `cd backend && uv run pytest -v -k "tenant_console"`
  - `cd backend && uv run pytest -v`
- Expected results:
  - Tenant console tests pass for both locales.

## Idempotence and Recovery

- Safe to re-run: tests.
- Rollback notes: revert i18n replacements to restore Spanish-only console.

## Exit Criteria

- [ ] Tenant console localized end-to-end.
- [ ] WhatsApp locale switch implemented + tested.
- [ ] `uv run pytest -v` green.

