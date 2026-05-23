# Phase 01: Locale persistence + i18n foundation + catalog API

## Objective

- Persist tenant locale (`en`/`es`) on tenant record with safe default/backfill.
- Provide backend i18n core + translation catalogs loaded in-memory.
- Provide authenticated endpoint for frontend to fetch effective locale catalog.

## Scope

- Files/modules this phase may touch:
  - `backend/app/models/tenant.py`
  - `backend/alembic/versions/*_add_tenant_locale.py` (new)
  - `backend/app/core/i18n.py` (new)
  - `backend/app/api/v1/endpoints/i18n.py` (new)
  - `backend/app/api/v1/router.py`
  - `backend/app/schemas/me.py`, `backend/app/services/profile_service.py`, `backend/app/api/v1/endpoints/me.py`
  - `backend/tests/conftest.py` (tenant fixture locale)
- Files/modules this phase must not touch:
  - `frontend/**` (defer)
  - `backend/app/services/whatsapp_*` (defer)

## Preconditions

- PRD accepted: `docs/brainstorms/260522-2330-python-i18n-system/SUMMARY.md`.
- Local dev environment can run backend tests (`uv` installed, deps synced).

## Tasks

1. Add tenant locale field
   - Update `backend/app/models/tenant.py`:
     - Add `locale: Mapped[str] = mapped_column(String(5), nullable=False, default="en", server_default="en")`.
     - Add comment-free; match existing style.
   - Add Alembic migration:
     - Add nullable column with server default `en`.
     - Backfill existing rows to `es` (preserve current Spanish experience).
     - Alter column to `nullable=False`.
     - Keep server default `en` for new rows.

2. Expose locale via `/me`
   - Update `backend/app/schemas/me.py` `ProfileResponse` to include `locale: str | None = None`.
   - Update `backend/app/api/v1/endpoints/me.py` `_profile_response()` to set:
     - For tenant role: `locale=profile.locale`.
     - For client role: `locale=profile.tenant.locale` (if loaded) else `None`.
     - For master role: `locale=None`.

3. Allow tenant to update locale via `/me`
   - Update `backend/app/schemas/me.py` `ProfileUpdate` to include `locale: str | None = None` with validator restricting to `en`/`es`.
   - Update `backend/app/services/profile_service.py`:
     - For tenant role allowed_fields add `locale`.
     - Ensure master cannot set locale (ignore field or raise PermissionError).
     - Ensure client remains read-only.

4. Implement backend i18n core (in-memory catalogs)
   - Create `backend/app/core/i18n.py`:
     - Constants: `SUPPORTED_LOCALES = {"en", "es"}`, `DEFAULT_LOCALE = "en"`.
     - `t(locale: str | None, key: str, **params) -> str`:
       - Normalize locale; unknown -> `DEFAULT_LOCALE`.
       - Lookup in locale catalog; if missing -> lookup in `DEFAULT_LOCALE`.
       - Missing key: warning log + increment in-memory counter (key+locale).
       - Apply `str.format(**params)` for named placeholders.
     - Formatting helpers for phase 1 (used later): `format_date`, `format_datetime`, `format_number`.
   - Create minimal catalogs inside module or as separate dicts:
     - Start with only keys needed for Phase 1 endpoint responses (eg `i18n.unsupported_locale`).
     - Defer large catalogs to later phases.

5. Add i18n catalog endpoint
   - Create `backend/app/api/v1/endpoints/i18n.py` with `router = APIRouter(prefix="/i18n", tags=["i18n"])`.
   - Endpoint: `GET /api/v1/i18n/catalog`
     - Auth: `CurrentUser` + `DbDep`.
     - Resolve effective locale:
       - tenant: from tenant profile (`Tenant.locale`).
       - client: resolve via client profile join to tenant (prefer `ProfileService.get_profile()` path) to avoid RLS surprises.
       - master: return `{ locale: "es", strings: {} }` or `{ locale: "es", strings: master-fixed }` (keep minimal; master i18n out-of-scope).
     - Return merged dict: `{"locale": <effective>, "strings": <merged_strings_for_locale_with_en_fallback>}`.
       - Implementation: precompute merged immutable dicts at import/startup (avoid mutating shared dicts per request).
   - Wire router into `backend/app/api/v1/router.py`.

6. Update tests for locale persistence contract
   - Update `backend/tests/conftest.py` tenant fixture to set `locale="es"` explicitly (represents existing tenant).
   - Add new tests:
     - New tenant created via `TenantService.create_tenant` defaults `en` (or direct ORM insert w/out locale sets `en`).
     - `/api/v1/me` for tenant returns locale.
     - `PUT /api/v1/me` with locale updates tenant record.

## Acceptance Criteria

- DB has `tenants.locale` non-null; new rows default `en`.
- Migration backfills existing rows to `es`.
- `/api/v1/me` exposes locale for tenant + client.
- Tenant can update locale via `/api/v1/me` (client cannot; master unaffected).
- `/api/v1/i18n/catalog` returns effective locale + strings payload.

## Verification

- Commands:
  - `cd backend && uv run pytest -v`
- Expected results:
  - All tests pass.
  - New tests cover locale persistence + `/me` update.
- Evidence to record in `SUMMARY.md`:
  - Pytest summary (pass count).

## Idempotence and Recovery

- Safe to re-run: tests, catalog endpoint.
- Recovery if interrupted: none.
- Rollback notes: alembic downgrade drops column (data loss acceptable only in non-prod).

## Exit Criteria

- [ ] Alembic migration exists and is correct.
- [ ] Backend models + `/me` updated.
- [ ] `/i18n/catalog` endpoint wired.
- [ ] `uv run pytest -v` green.

