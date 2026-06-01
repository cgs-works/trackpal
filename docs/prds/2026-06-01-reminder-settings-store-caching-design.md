# Spec: Timezone and Reminder Settings Caching in AuthStore

This document defines the frontend architectural specifications to cache subscription reminder settings and timezone options in the global Pinia `useAuthStore`. This prevents repeated network requests to `/subscription-settings` and `/subscription-settings/timezones` when the "Reminder Settings" modal is opened or closed, ensuring an instantaneous and robust user experience.

## Context & Current Behavior

Currently, `ReminderSettingsModal.vue` is a self-fetching modal:
- When the modal is shown, it watches the `show` prop and executes both `loadTimezones()` and `loadSettings()` concurrently.
- This creates 2 HTTP GET requests every time the modal is opened, even if no settings or timezones have changed.
- If a user opens the modal, closes it, and opens it again, it makes 2 more requests.
- There is no global state sharing of these settings; other views cannot access the tenant's reminder configuration without querying the backend directly.

## Requirements & Constraints

0. **Scope Control**: `SubscriptionsView.vue` is already oversized, but this PRD does not include a full view refactor. Keep changes surgical and limited to removing redundant reminder settings state and wiring the store-backed modal. Track broader decomposition separately.
1. **Pragmatic Caching**: Cache the `reminderSettings` object and the `timezoneOptions` list in the global `useAuthStore` Pinia store as one tenant-context bundle. These fields are runtime-only and must not be persisted to `localStorage`.
2. **Route-Scoped Upfront Loading**: Trigger the load once when initializing `SubscriptionsView` (in `init()`). Do not preload from `TenantDashboardView`; users may visit the dashboard without using subscriptions, and the modal still has a store-backed fallback load if opened before the preload completes.
3. **Network Request Deduplication**: Use a promise tracker (`_settingsPromise`) in the store to ensure that if concurrent loads are triggered (e.g., fast navigation or multiple hooks), only 1 HTTP request is performed.
4. **Context-Scoped Lifetime**: Within the same tenant context, cached reminder settings and timezone options remain valid until logout, tenant switch, or support-context exit. There is no TTL and no refresh-on-open in this PRD.
5. **Stale State Isolation**: The cache must be cleared immediately when switching tenants, exiting support context, or logging out.
6. **Draft Modifiability**: The modal must NOT mutate the global cache *while* editing. It must clone the cached settings on open, allowing the user to modify values locally. Saving updates the store and backend, while cancelling discards any local mutations.
7. **Robust Error Gating**: Treat settings + timezone loading as an all-or-retry unit. If either request fails, the store does not mark either cache as loaded, enabling retries on subsequent accesses and avoiding partially initialized UI state.

---

## Architectural Design

### 1. Pinia Store Extension (`frontend/src/stores/auth.js`)

We will add the following runtime-only properties to the reactive state of `useAuthStore`. This keeps the change small because `authStore` already owns the authentication lifecycle where tenant-scoped cache invalidation must happen (`logout`, `switchTenant`, `exitTenantContext`).

```js
// Cache State
const reminderSettings = ref(null)
const timezoneOptions = ref([])
const reminderSettingsLoaded = ref(false)
const timezonesLoaded = ref(false)

// Promise tracker for request deduplication
const _settingsPromise = ref(null)
const _settingsContextKey = ref(null)
```

We will implement the following actions:

#### `loadTenantSettings(force = false)`
Fetches both reminder settings and supported timezones as a single tenant-context bundle. Deduplicates concurrent requests and guards against late responses from a previous tenant context. Even when `force = true`, an existing in-flight request for the same context is reused rather than duplicated. Even though the timezone catalog endpoint is effectively global, this PRD keeps it bundled with settings to avoid separate loaded/error states.

```js
function getTenantSettingsContextKey() {
  // Master support mode has an explicit active tenant.
  // Direct tenant sessions do not currently expose tenant_id in UserInfo,
  // so user.id is the stable per-login cache isolation key without backend changes.
  return activeTenantId.value || user.value?.id || null
}

async function loadTenantSettings(force = false) {
  const contextKey = getTenantSettingsContextKey()

  if (!force && reminderSettingsLoaded.value && timezonesLoaded.value) {
    return
  }

  if (_settingsPromise.value && _settingsContextKey.value === contextKey) {
    return _settingsPromise.value
  }

  _settingsContextKey.value = contextKey
  _settingsPromise.value = (async () => {
    try {
      const [settingsRes, tzRes] = await Promise.all([
        api.get('/subscription-settings'),
        api.get('/subscription-settings/timezones')
      ])

      if (_settingsContextKey.value !== contextKey) {
        return
      }

      reminderSettings.value = settingsRes.data
      timezoneOptions.value = tzRes.data || []
      reminderSettingsLoaded.value = true
      timezonesLoaded.value = true
    } catch (error) {
      // All-or-retry: leave both loaded flags false so later access can retry.
      throw error
    } finally {
      if (_settingsContextKey.value === contextKey) {
        _settingsPromise.value = null
      }
    }
  })()

  return _settingsPromise.value
}
```

#### `updateTenantReminderSettings(settingsData)`
Saves updated settings to the database and refreshes the cache only with the server response. Do not optimistically update before the `PUT` succeeds, and do not force a follow-up `GET` if the `PUT` returns the normalized settings.

```js
async function updateTenantReminderSettings(settingsData) {
  const response = await api.put('/subscription-settings', settingsData)
  reminderSettings.value = response.data
  reminderSettingsLoaded.value = true
  return response.data
}
```

#### `clearTenantSettings()`
Resets all cached tenant properties to their default values.

```js
function clearTenantSettings() {
  reminderSettings.value = null
  timezoneOptions.value = []
  reminderSettingsLoaded.value = false
  timezonesLoaded.value = false
  _settingsPromise.value = null
  _settingsContextKey.value = null
}
```

This helper must be called inside:
- `login(username, password)` at the start, before applying the new identity
- `logout()` at the start
- `switchTenant(tenantId)` at the start
- `exitTenantContext()` at the start

### 2. Dashboard Loading Trigger (`frontend/src/views/TenantDashboardView.vue`)

Do not add reminder settings preload to the dashboard. Reminder settings are subscription-specific state, and loading them from the dashboard would add two subscription settings requests for tenants who never open the subscriptions area.

### 3. Subscriptions View Orchestration (`frontend/src/views/SubscriptionsView.vue`)

Remove dead and redundant local state:
- Delete `reminderSettings` local ref.
- In `init()`, call `authStore.loadTenantSettings()` as a silent, non-blocking preload relative to the page's main subscription data.
- If preload fails, do not show a page-level error; the modal will retry and display a contextual error if opened.
- Pass properties from `authStore` to the modal component.

```js
// Inside SubscriptionsView.vue init()
async function init() {
  await Promise.all([
    loadClients(),
    loadServices(),
    authStore.loadTenantSettings().catch(() => {}) // silent preload; modal retries on open
  ])
  await buildPlanMap()
  ...
}
```

Template binding:
```html
<ReminderSettingsModal
  :show="showReminderSettings"
  @close="closeModals"
/>
```

Do not reload subscriptions after saving reminder settings; these settings do not mutate subscription rows. The successful `PUT` response updates the store cache directly.

### 4. Presentation and Local Mutation (`frontend/src/components/subscriptions/ReminderSettingsModal.vue`)

The modal receives its reactive options and initial values from `authStore` and manages a cloned draft locally.

- Remove the props: `initialSettings`.
- Import `useAuthStore` in `ReminderSettingsModal.vue`.
- Add an `isLoadingSettings` ref used only for the first/open-time fallback load.
- If the user opens the modal before preload finishes, show an inline loading state and disable Save until the store load resolves; do not show default values as if they were persisted settings.
- Inside `watch(() => props.show)`, await `authStore.loadTenantSettings()` and then deep-clone `authStore.reminderSettings` to local `settings.value`:

```js
const authStore = useAuthStore()

watch(
  () => props.show,
  async (newVal) => {
    if (newVal) {
      errorMessage.value = ''
      loadError.value = ''
      customDay.value = ''
      
      try {
        isLoadingSettings.value = true
        // Ensure settings are loaded in memory; dedupes with SubscriptionsView preload.
        await authStore.loadTenantSettings()
        
        // Deep clone the cached store settings to the local draft
        settings.value = {
          reminders_enabled: authStore.reminderSettings?.reminders_enabled ?? false,
          timezone: authStore.reminderSettings?.timezone || 'UTC',
          warning_days: [...(authStore.reminderSettings?.warning_days || [7, 3, 1])],
          reminder_time: authStore.reminderSettings?.reminder_time || '09:00',
          recipient_mode: authStore.reminderSettings?.recipient_mode || 'tenant_only',
        }
      } catch (error) {
        loadError.value = getApiError(error, i18nStore.t('frontend.subscriptions.error_load_settings'))
      } finally {
        isLoadingSettings.value = false
      }
    }
  }
)
```

Dropdown options read directly from the reactive store properties:
- `timezoneOptions` is read from `authStore.timezoneOptions`.
- Save action delegates to `authStore.updateTenantReminderSettings(settings.value)` and closes the modal without asking the parent to reload subscriptions:

```js
async function saveSettings() {
  if (loadError.value || isLoadingSettings.value) return

  isSaving.value = true
  errorMessage.value = ''
  try {
    await authStore.updateTenantReminderSettings(settings.value)
    emit('close')
  } catch (error) {
    errorMessage.value = getApiError(error, i18nStore.t('frontend.subscriptions.error_reminder_settings'))
  } finally {
    isSaving.value = false
  }
}
```

---

## Verification & Test Plan

### Automatic Checks
1. Add Vitest-only frontend store tests for `useAuthStore` reminder settings caching. This PRD may introduce `vitest` and a `test` script in `frontend/package.json`, but should not introduce Vue Test Utils or browser E2E infrastructure.
2. Test the store with mocked Axios/localStorage for:
   - first `loadTenantSettings()` performs exactly one GET to `/subscription-settings` and one GET to `/subscription-settings/timezones`;
   - concurrent `loadTenantSettings()` calls reuse the same promise and do not duplicate GET requests;
   - failed load does not mark either cache as loaded and allows a later retry;
   - `updateTenantReminderSettings()` updates cache from `PUT` response only;
   - `clearTenantSettings()` resets data, loaded flags, promise tracker, and context key;
   - late responses from a previous context key do not repopulate stale cache.
3. Run the frontend tests:
   ```bash
   cd frontend && npm test
   ```
4. Compile and build the frontend production assets:
   ```bash
   cd frontend && npm run build
   ```
5. Verify that there are no static analyzer or bundler errors related to Pinia store bindings or prop removals.

### Manual Verification Flows
1. **Initial Login/Dashboard**: Login as a tenant and land on the dashboard. Observe the Network tab. Ensure no requests are sent to `/subscription-settings` or `/subscription-settings/timezones` from dashboard mount.
2. **Subscriptions Route Preload**: Navigate to "Subscriptions". Ensure exactly one request is sent to `/subscription-settings` and exactly one request is sent to `/subscription-settings/timezones` during route initialization.
3. **Settings Modal Interaction After Preload**: Open the "Reminder Settings" modal after route preload completes.
   - Observe that the modal opens instantly with no loader and NO additional GET requests.
   - Toggle values (e.g. deactivate reminders) and close the modal WITHOUT saving. Ensure that when reopened, the values revert to their original database-backed state.
   - Toggle values and click "Save". Ensure a `PUT` request is sent, the modal closes, and reopening it displays the saved values instantly.
4. **Settings Modal Interaction During Preload**: Throttle the network, navigate to "Subscriptions", and immediately open the modal before preload finishes. Verify that the modal shows inline loading, Save is disabled, and the final form uses server-backed settings once loaded.
5. **Master Tenant Context Switching**: Log in as Master. Switch context into Tenant A. Open Settings. Save some changes. Switch context into Tenant B. Open Settings. Verify that Tenant B's settings are fetched fresh and do not display cached values from Tenant A.
