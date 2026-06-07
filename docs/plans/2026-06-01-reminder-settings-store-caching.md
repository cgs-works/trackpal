# PRD: Reminder Settings Store Caching

## Problem Statement

Tenant users and Master users operating in a Tenant Context currently experience unnecessary network requests when opening and closing Reminder Settings. The modal owns its own data loading, so every open triggers requests for Reminder Settings and timezone options even when the same Tenant Context has already loaded them.

This makes the modal feel slower than necessary, increases frontend/backend traffic, and creates a stale-state risk when Master switches between tenant support contexts. Users need Reminder Settings to feel instant after entering the subscriptions area while still protecting each tenant's data from leaking across Tenant Context boundaries.

## Solution

Move Reminder Settings and timezone options into a runtime-only Pinia cache owned by the authentication store. Load the cache once when the subscriptions area initializes, reuse the same in-flight promise for concurrent loads, and clear the cache whenever identity or Tenant Context changes.

The Reminder Settings modal will no longer fetch settings and timezones independently on every open. Instead, it will read from the store, clone the cached Reminder Settings into a local draft when opened, and save through a store action that updates the cache from the backend response. If the user opens the modal before the route preload finishes, the modal will show inline loading and disable Save until server-backed settings are available.

## User Stories

1. As a tenant user, I want Reminder Settings to open instantly after I enter Subscriptions, so that I can adjust reminder behavior without waiting on repeated network calls.
2. As a tenant user, I want opening and closing Reminder Settings repeatedly to reuse cached data, so that the modal does not become slower or noisier over time.
3. As a tenant user, I want the dashboard to avoid loading subscription-specific settings, so that visiting the dashboard does not trigger unnecessary subscription requests.
4. As a tenant user, I want the subscriptions area to preload Reminder Settings once, so that the modal is ready by the time I need it.
5. As a tenant user, I want the modal to show a loading state if I open it before preload finishes, so that I do not edit placeholder defaults by mistake.
6. As a tenant user, I want Save disabled while Reminder Settings are still loading, so that I cannot submit incomplete or default data accidentally.
7. As a tenant user, I want cancelling the modal to discard unsaved edits, so that experimenting with settings does not mutate the real tenant configuration.
8. As a tenant user, I want saved changes to appear immediately when I reopen the modal, so that I can trust that the update succeeded.
9. As a tenant user, I want failed settings loads to be retried later, so that a transient error does not permanently break Reminder Settings for the session.
10. As a tenant user, I want timezone options to load from the backend once per Tenant Context, so that I can choose from the supported IANA timezone catalog without repeated requests.
11. As a tenant user, I want the timezone dropdown to use backend-provided labels, so that offsets and names match the server's reminder scheduling rules.
12. As a tenant user, I want saving Reminder Settings to avoid reloading unrelated subscriptions, so that changing reminder behavior does not make the subscription list refresh unnecessarily.
13. As a tenant user, I want the cache to reset on logout, so that a later login cannot see the previous user's Reminder Settings.
14. As a tenant user, I want the cache to reset on a new login, so that changing identity in the same browser session starts cleanly.
15. As a Master user, I want the cache to reset when I switch into a tenant, so that I only see Reminder Settings for the active Tenant Context.
16. As a Master user, I want the cache to reset when I switch from Tenant A to Tenant B, so that Tenant A settings never appear in Tenant B's modal.
17. As a Master user, I want the cache to reset when I exit tenant support mode, so that tenant-scoped Reminder Settings are not retained outside that Tenant Context.
18. As a Master user, I want late responses from a previous Tenant Context to be ignored, so that slow network responses cannot repopulate stale settings after switching tenants.
19. As a frontend maintainer, I want concurrent settings loads to deduplicate requests, so that route preload and modal fallback do not double-fetch the same data.
20. As a frontend maintainer, I want the cache to be runtime-only, so that persisted authentication data remains separate from derived tenant-scoped UI data.
21. As a frontend maintainer, I want Reminder Settings and timezone options treated as one loading bundle, so that the modal does not enter a partially initialized state.
22. As a frontend maintainer, I want the store update to use the server's PUT response, so that frontend cache reflects backend validation and normalization.
23. As a frontend maintainer, I want no optimistic cache update for Reminder Settings, so that rejected saves cannot leave invalid data in the UI.
24. As a frontend maintainer, I want no forced GET after a successful save, so that the app avoids redundant requests when the PUT already returns the normalized settings.
25. As a frontend maintainer, I want store-level tests around caching and deduplication, so that future changes do not reintroduce repeated requests or stale Tenant Context behavior.
26. As a frontend maintainer, I want to avoid a large subscriptions view refactor in this change, so that the caching improvement remains focused and safe.
27. As a support operator, I want manual verification steps for Tenant Context switching, so that cross-tenant stale state is explicitly checked before release.
28. As a product owner, I want Reminder Settings caching to improve perceived speed without changing backend contracts, so that the feature can ship with low backend risk.

## Implementation Decisions

- Use the existing authentication Pinia store as the owner of runtime Reminder Settings cache because it already owns login, logout, tenant switching, and support-context exit behavior.
- Cache Reminder Settings and timezone options as a single Tenant Context bundle.
- Do not persist Reminder Settings, timezone options, loaded flags, in-flight promises, or context keys to localStorage.
- Do not preload Reminder Settings from the tenant dashboard. The dashboard is not subscription-specific, and loading settings there would create unnecessary traffic for users who never visit subscriptions.
- Preload Reminder Settings from subscriptions initialization as a silent preload. A preload failure must not block subscriptions data or show a page-level error.
- Keep the modal as the fallback load seam. If route preload has not completed, the modal calls the same store load action and reuses any in-flight promise.
- Treat the settings/timezones load as all-or-retry. If either request fails, neither cache should be marked loaded.
- Use a promise tracker to deduplicate concurrent loads for the same Tenant Context.
- Even when a forced load is requested, reuse an existing in-flight request for the same Tenant Context rather than creating duplicate network calls.
- Derive the frontend Tenant Context cache key from the active tenant id when Master is operating in support mode, otherwise from the current user id. This avoids a backend contract change because direct tenant sessions do not currently expose tenant id in the auth user payload.
- Guard late responses with the Tenant Context key. A response that resolves after the context key changes must not write settings or timezones into the current cache.
- Clear the cache at the start of login, logout, tenant switch, and support-context exit.
- Keep cache lifetime scoped to the current Tenant Context. There is no TTL and no refresh-on-open in this PRD.
- Remove redundant local Reminder Settings state from the subscriptions view.
- Remove the modal's initial settings prop and direct self-fetching behavior.
- When opening the modal, deep-clone cached Reminder Settings into a local draft before editing.
- The modal must not mutate global store state while the user is editing.
- Cancelling or closing the modal without saving must discard local draft changes.
- Saving Reminder Settings must call the store update action.
- The store update action must update cache only from the successful server response.
- Do not perform an optimistic update before the PUT succeeds.
- Do not force a follow-up GET after PUT if the PUT response contains the normalized Reminder Settings.
- Do not reload subscriptions after saving Reminder Settings because Reminder Settings do not mutate subscription rows.
- The modal should show inline loading and disable Save when opened before settings are available.
- The modal should show a contextual load error if the fallback load fails.
- The timezone dropdown should read options from the store and use backend-provided option values and labels.
- Introduce Vitest only for frontend store tests. Do not introduce Vue Test Utils or browser E2E infrastructure for this PRD.
- Keep the change surgical even though the subscriptions view is oversized. Broader view decomposition is a separate concern.
- No backend schema changes are required.
- No backend API contract changes are required.

## Testing Decisions

- Good tests should verify observable behavior: request counts, returned cache state, retry behavior, context isolation, and modal-facing store outcomes. Tests should avoid coupling to implementation details beyond the public store actions and exposed store state needed by the UI.
- The highest automated seam for this PRD is the Pinia auth store because the core risk is cache lifecycle, request deduplication, and Tenant Context isolation.
- Add Vitest-only frontend tests with mocked Axios and localStorage.
- Test that the first load performs exactly one request to Reminder Settings and one request to the timezone catalog.
- Test that concurrent loads for the same Tenant Context reuse one promise and do not duplicate GET requests.
- Test that failed loads do not mark settings or timezones as loaded and allow a later retry.
- Test that updating Reminder Settings writes the cache from the PUT response only.
- Test that clearing tenant settings resets cached data, loaded flags, the in-flight promise, and the context key.
- Test that a late response from a previous Tenant Context does not repopulate stale cache after the context changes.
- Run the frontend test script as part of verification.
- Run the frontend production build as part of verification.
- Manual verification should cover dashboard no-preload behavior, subscriptions preload behavior, modal open after preload, modal open during preload, save behavior, cancel behavior, and Master Tenant Context switching.
- Prior art in this codebase is limited for frontend tests because the frontend currently has no test script. This PRD intentionally introduces the smallest frontend test seam necessary: store-level Vitest tests, not component or E2E tests.

## Out of Scope

- Refactoring the entire subscriptions view into smaller components or composables.
- Adding Vue Test Utils component tests.
- Adding Playwright or browser E2E tests.
- Changing backend Reminder Settings endpoints.
- Changing backend timezone catalog sourcing.
- Adding a TTL for Reminder Settings or timezone cache.
- Refreshing Reminder Settings every time the modal opens.
- Persisting Reminder Settings cache to localStorage.
- Adding optimistic updates for Reminder Settings saves.
- Reloading subscriptions after Reminder Settings are saved.
- Adding tenant id to the auth user payload.
- Changing Reminder Settings database schema.
- Changing n8n reminder workflow behavior.

## Further Notes

- Domain language should use Reminder Settings for the tenant-owned reminder configuration and Tenant Context for the active tenant scope.
- The timezone catalog is effectively global, but this PRD deliberately caches it with Reminder Settings as one Tenant Context bundle to keep loading and error behavior simple.
- The subscriptions view is known to be oversized. This PRD should reduce redundant local state but should not become a broad frontend architecture cleanup.
- The existing design notes remain useful for implementation detail, but this PRD is the product and engineering contract for the work.
