# Implementation Plan: Python-centered i18n system (tenant locale)

> Created: 2026-05-23 00:41:43

## Purpose / Big Picture

- Deliver end-to-end i18n for tenant/client-facing system text across backend, Vue dashboard, tenant WhatsApp console, n8n outbound reminders.
- Python backend becomes translation source-of-truth; tenant locale persisted in DB; English default + fallback.
- Brainstorm/PRD: `docs/brainstorms/260522-2330-python-i18n-system/SUMMARY.md`.
- Tracking issue: `#15` — https://github.com/neutrobox/trackpal/issues/15

## Objective

- Add `tenants.locale` with safe migration/backfill.
- Add backend i18n engine + catalogs for `en` + `es` (code files, in-memory).
- Add backend contract for frontend translation catalog fetch; refetch on locale change.
- Localize tenant WhatsApp console + reminder payload messages using tenant locale.
- Systematic audit + replace hardcoded tenant/client-visible strings in backend, frontend, n8n.

## Context and Orientation

- Relevant docs loaded:
  - `docs/code-standard/backend-conventions.md`
  - `docs/code-standard/frontend-conventions.md`
  - `docs/architecture/whatsapp-console-flow.md`
  - `docs/architecture/n8n-workflow.md`
- Relevant files/modules:
  - Backend: `backend/app/models/tenant.py`, `backend/app/services/*`, `backend/app/api/v1/endpoints/*`, `backend/app/api/v1/router.py`
  - WhatsApp tenant console: `backend/app/services/whatsapp_tenant_console_service.py`, `backend/app/services/whatsapp_tenant_console_facade.py`
  - Reminders: `backend/app/services/subscription_job_service.py`, `backend/app/api/v1/endpoints/subscriptions.py`
  - Frontend: `frontend/src/views/*.vue`, `frontend/src/stores/auth.js`, `frontend/src/services/api.js`
  - n8n: `n8n/Trackpal WhatsApp Bot.json`, `n8n/Trackpal Subscription Reminders.json`
- Existing patterns to follow:
  - Backend services raise `ValueError` -> endpoints map to `HTTPException(detail=str(exc))`.
  - WhatsApp flows store session state in Redis; reply templates currently class constants (Spanish).
- Constraints, dependencies, compatibility notes:
  - Phase 1 locales only: `en`, `es`.
  - New tenants default `en`.
  - Existing tenants must keep Spanish experience via migration/backfill (`es`).
  - Master internal UI + master WhatsApp console remain fixed Spanish (out of i18n scope).

## Scope

### In scope

- Persist tenant locale on `tenants` record; expose via `/me`.
- Tenant locale change via:
  - Web dashboard (tenant profile/settings)
  - Tenant WhatsApp console profile/settings
- Backend i18n engine:
  - Named placeholder templates (`{tenant_name}`, `{days_left}`, ...)
  - Missing key fallback to English + warning logs + in-memory counter.
  - In-memory catalogs (no per-request disk I/O).
  - Explicit `locale` parameter in translation primitive.
- Backend-to-frontend i18n contract:
  - New endpoint to fetch merged locale catalog for logged-in user.
  - Frontend fetch at login + refetch immediately after locale change.
- Localize tenant-facing WhatsApp console text.
- Localize subscription reminder message generation (n8n transport sends backend-rendered message).
- Systematic audit of hardcoded tenant/client-visible strings across backend, frontend, n8n.

### Out of scope

- Client-specific locale preference (per-client override).
- Master internal dashboard/console i18n (master stays Spanish).
- Translating user-authored business data (service/plan names, client names, etc).
- Translation CMS / DB-managed translations.
- Locales beyond `en`/`es`.

## Architecture & Approach

- Backend i18n module under `backend/app/core/`:
  - Catalogs as Python dicts in code (versioned), loaded at import.
  - `t(locale, key, **params)` returns formatted string with fallback to `en`.
  - Missing key event: `logger.warning` + `Counter` increment (no sensitive content).
  - Formatting helpers for phase 1 locale-sensitive date/number formatting used in backend-generated messages.
  - Catalog safety:
    - Treat catalogs as immutable.
    - Precompute merged `en`-fallback catalogs per locale at startup (avoid per-request mutation/cache pollution).
- Tenant locale resolution:
  - Stored as `tenants.locale`.
  - API requests: resolve locale from tenant record using `current_user` + `active_tenant_id` context.
  - Background/API-key flows (n8n): resolve tenant locale from DB using internal RLS context.
- Frontend:
  - Maintain no local translation strings as source-of-truth; store only translation keys.
  - Load backend-provided catalog into Pinia i18n store; `t(key, params)` helper.
  - Date/number formatting (PRD FR-15): backend must provide formatted display strings for tenant/client-visible values in web UI.
- WhatsApp tenant console:
  - Replace Spanish class-constant templates with runtime `t(locale, key)` lookups.
  - Ensure locale lookup happens per message (no caching that delays updates).

## Progress

- [x] Plan approved for execution.
- [x] **Phase 1 [M]: Locale persistence + i18n foundation + catalog API** — Complete.
  - `tenants.locale` column already existed (migration `cd8efe74caa1` with proper backfill).
  - i18n engine at `app/core/i18n.py` with `t()`, `get_merged_catalog()`, full EN + ES catalogs, merged en-fallback.
  - `/api/v1/i18n/catalog` endpoint at `app/api/v1/endpoints/i18n.py`, wired in router.
  - Profile schemas (`ProfileResponse`, `ProfileUpdate`) include `locale` with Pydantic validation.
  - `/me` endpoint passes `locale` from tenant record in response.
  - Profile service allows `locale` update for tenant role.
  - **Verification:** 769 passed, 1 skipped. 19 i18n-specific tests added.
- [x] **Phase 2 [L]: Backend user-facing translations (API errors + reminders)** — Complete.
  - New `app/core/errors.py`: `UserFacingError(ValueError)` + `translate_error()` helper.
  - i18n catalogs expanded: 19 new error keys + updated reminder template.
  - Services refactored: client, catalog, subscription, profile raise `UserFacingError`.
  - `resolve_locale()` helper in `app/api/dependencies.py`.
  - Endpoints catch `UserFacingError` before `ValueError` and translate via `t()`.
  - `SubscriptionJobService._render_reminder_message` uses `t()` with tenant locale.
  - **Verification:** 769 passed, 1 skipped (no regressions).
- [x] **Phase 3 [XL]: Tenant WhatsApp console localization + locale switch flow** — Complete.
  - 94 string constants replaced with i18n key constants.
  - `_t()` helper + `ContextVar` for per-message locale resolution.
  - Facade resolves `tenant.locale` and passes to console service.
  - Added locale switch flow in WhatsApp profile menu.
  - 108 `wa.tenant.*` i18n keys in both EN + ES catalogs.
  - **Verification:** 769 passed, 1 skipped (no regressions).
- [x] **Phase 4 [L]: Frontend i18n + locale switch UI** — Complete.
  - New `frontend/src/stores/i18n.js` (Pinia store: `loadCatalog()`, `t(key, params)`).
  - Catalog auto-loaded at login (LoginView) and on page refresh (main.js).
  - Tenant locale selector in profile section, refetches catalog on save.
  - Hardcoded strings replaced with `t()` keys in LoginView, TenantDashboardView, ClientDashboardView, SubscriptionsView.
  - 120 frontend i18n keys (`frontend.*`) added to backend catalogs (EN + ES).
  - **Verification:** `npm run build` passes.
- [x] Phase 5 [M]: Audit + n8n cleanup + final verification
  - Audit: 53 hardcoded error strings in `whatsapp_tenant_console_service.py` → `self._t()` keys.
  - Endpoints: `Service not found`, `Client not found`, `Plan not found`, `Subscription not found`, `Profile not found`, `Incorrect old password`, `Reminder log not found` → locale-aware `_t()` calls.
  - Frontend: remaining fallback strings in `SubscriptionsView.vue` → `i18nStore.t()` calls.
  - Added 25 `wa.tenant.errors.*` keys + 11 `errors.*` keys + 19 `frontend.*` error keys to EN + ES catalogs.
  - n8n workflows verified as pure transport.
  - **Verification:** 769 passed, 1 skipped; `npm run build` passes.

## Phases

- [x] **Phase 1 [M]: Locale persistence + i18n foundation + catalog API** — add `tenants.locale`, migration/backfill, i18n core, `/i18n/catalog`.
- [x] **Phase 2 [L]: Backend user-facing translations (API errors + reminders)** — introduce user-facing error codes + translation; localize reminder payload messages; formatting helpers.
- [x] **Phase 3 [XL]: Tenant WhatsApp console localization + locale switch flow** — runtime i18n lookups across tenant console + facade; add WhatsApp locale change option.
  - 94 string constants replaced with i18n key constants.
  - `_t()` helper + `ContextVar` for per-message locale resolution.
  - Facade resolves `tenant.locale` and passes to console service.
  - Added locale switch flow in WhatsApp profile menu.
  - 108 `wa.tenant.*` i18n keys in both EN + ES catalogs.
  - Facade-level replies (`INACTIVE_TENANT_REPLY`, etc.) localized via `wa.tenant.facade.*` keys.
  - Client list/detail format methods localized.
  - **Verification:** 769 passed, 1 skipped.
- [x] **Phase 4 [L]: Frontend i18n + locale switch UI** — i18n store, refactor tenant/client views strings to keys, add language selector, refetch catalog.
  - New `frontend/src/stores/i18n.js` Pinia store with `loadCatalog()` and `t(key, params)`.
  - Catalog loaded at login (LoginView) and on page refresh if authenticated (main.js).
  - Tenant locale `<select>` in profile section; refetches catalog on save for immediate update.
  - Replaced hardcoded strings with `t()` calls in LoginView, TenantDashboardView, ClientDashboardView, SubscriptionsView.
  - 120 `frontend.*` keys added to both EN and ES backend catalogs.
  - **Verification:** `npm run build` passes.
- [x] **Phase 5 [M]: Audit + n8n cleanup + final verification** — systematic hardcoded-string sweep; update n8n fallback if needed; run tests/build; manual QA.

## Key Changes

- DB:
  - Add `tenants.locale` (non-null) + server default `en` + backfill existing rows to `es`.
- Backend:
  - New i18n module + catalogs.
  - New endpoint `/api/v1/i18n/catalog`.
  - Update `/me` schemas to expose locale; update profile update flow to allow locale change for tenant role.
  - Introduce `UserFacingError` (code + params) and translate at API boundary.
  - Update reminder message generation to use i18n templates.
  - Localize WhatsApp tenant console replies.
- Frontend:
  - Add i18n store + helper.
  - Refactor strings to keys; use backend catalog.

## Validation and Acceptance

- Backend verify:
  - `cd backend && uv run pytest -v`
- Frontend verify:
  - `cd frontend && npm run build`
- Manual QA (must-do):
  - Tenant web: switch `en ↔ es` in profile/settings; text updates immediately; refresh persists.
  - Tenant WhatsApp console: switch `en ↔ es` inside active session; next reply uses new locale.
  - Reminder payload endpoint returns message localized per tenant locale.
  - Missing `es` key shows English fallback; warning log emitted; counter increments.

## Idempotence and Recovery

- Migrations:
  - Safe rerun: Alembic migrations must be deterministic.
  - Rollback: downgrade migration removes `tenants.locale` (data loss acceptable only in dev).
- i18n catalogs:
  - Adding keys safe; removing keys requires audit + tests.

## Dependencies

- None required if phase 1 formatting uses simple locale-specific formatting helpers.
- If executor chooses Babel instead, add `babel` to `backend/pyproject.toml` (plan prefers no new deps for phase 1).

## Risks & Mitigations

- Large WhatsApp console string surface (4k LOC) -> mitigate via phased replacement + tests per flow + systematic rg audit.
- API error message localization regression -> mitigate by introducing `UserFacingError` with codes; tests assert codes/translated output per locale.
- Locale change not immediate in WhatsApp -> mitigate by resolving locale per message from DB (no session caching).
- Missing keys -> fallback to English + warning + counter; add audit step to keep keys complete.
- Perf overhead -> O(1) dict lookup + `str.format`; avoid file I/O; avoid per-request catalog rebuild.
- Multi-worker missing-key counters -> counters per-process only; rely on structured warning logs for aggregation.

## Surprises & Discoveries

- Phase 1 already fully implemented before execution start. `tenants.locale`, migration, i18n engine, catalog endpoint, schema, and `/me` wiring were all committed. Only gap found: none — everything was wired correctly including i18n router import.
- Phase 5 audit found ~53 hardcoded error strings in WhatsApp console service, plus ~40 hardcoded endpoint strings and ~4 frontend fallback strings. All were converted to i18n keys.
- `create_subscription` endpoint was missing `UserFacingError` handler (only caught `ValueError`), causing error codes (not translated messages) in API responses. Fixed.

## Decision Log

- 2026-05-23: Phase 1 pre-existing. No changes needed beyond plan progress update and verification. Decision: Mark Phase 1 complete, proceed to Phase 2.
- 2026-05-23: Phase 5 audit found remaining hardcoded strings. All fixed: 53 WhatsApp console error strings, 11 API endpoint strings, 4 frontend fallback strings. Decision: fix as part of Phase 5 scope.

## Outcomes & Retrospective

- To be completed by executor after final verification.

## Open Questions

- None (PRD states all decisions resolved). Only remaining action: confirm plan vs request edits.

