## Iteration 1 — 2026-06-01 17:33

**Item:** Install Vitest and setup initial auth store cache state

**Rationale:** First item in the plan prioritization — foundational setup needed before load/dedup/save actions.

**Changes:**
- `frontend/vite.config.js` — added `test` config with jsdom environment and globals
- `frontend/package.json` — added `vitest` devDependency and `"test": "vitest run"` script
- `frontend/src/stores/auth.js` — added reminder settings cache state (`reminderSettings`, `timezoneOptions`, `settingsLoaded`, `timezonesLoaded`, `settingsInFlight`, `tenantContextKey`, `settingsLoadError`), `_clearTenantSettingsCache()`, `_deriveTenantContextKey()`, and cache-clearing calls at start of `login`, `logout`, `switchTenant`, and `exitTenantContext`
- `frontend/src/stores/__tests__/auth.spec.js` — 9 tests covering initial cache state, `_clearTenantSettingsCache`, `_deriveTenantContextKey`, and cache reset on each auth action

**Verification:**
- `npm run test` — 9/9 passed, 1 file
- `npm run build` — production build succeeds, 112 modules, no warnings

**Next:** Item 2 — Implement store actions for loading and saving settings with context isolation.
