# Spec: Timezone and Reminder Settings Caching in AuthStore

This document defines the frontend architectural specifications to cache subscription reminder settings and timezone options in the global Pinia `useAuthStore`. This prevents repeated network requests to `/subscription-settings` and `/subscription-settings/timezones` when the "Reminder Settings" modal is opened or closed, ensuring an instantaneous and robust user experience.

## Context & Current Behavior

Currently, `ReminderSettingsModal.vue` is a self-fetching modal:
- When the modal is shown, it watches the `show` prop and executes both `loadTimezones()` and `loadSettings()` concurrently.
- This creates 2 HTTP GET requests every time the modal is opened, even if no settings or timezones have changed.
- If a user opens the modal, closes it, and opens it again, it makes 2 more requests.
- There is no global state sharing of these settings; other views cannot access the tenant's reminder configuration without querying the backend directly.

## Requirements & Constraints

1. **Pragmatic Caching**: Cache the `reminderSettings` object and the `timezoneOptions` list in the global `useAuthStore` Pinia store.
2. **On-Demand Upfront Loading**: Trigger the load once when entering the `TenantDashboardView` (on mounted) and/or when initializing the `SubscriptionsView` (in `init()`).
3. **Network Request Deduplication**: Use a promise tracker (`_settingsPromise`) in the store to ensure that if concurrent loads are triggered (e.g., fast navigation or multiple hooks), only 1 HTTP request is performed.
4. **Stale State Isolation**: The cache must be cleared immediately when switching tenants, exiting support context, or logging out.
5. **Draft Modifiability**: The modal must NOT mutate the global cache *while* editing. It must clone the cached settings on open, allowing the user to modify values locally. Saving updates the store and backend, while cancelling discards any local mutations.
6. **Robust Error Gating**: If fetching settings fails, the store does not mark them as loaded, enabling retries on subsequent accesses.

---

## Architectural Design

### 1. Pinia Store Extension (`frontend/src/stores/auth.js`)

We will add the following properties to the reactive state of `useAuthStore`:

```js
// Cache State
const reminderSettings = ref(null)
const timezoneOptions = ref([])
const reminderSettingsLoaded = ref(false)
const timezonesLoaded = ref(false)

// Promise tracker for request deduplication
const _settingsPromise = ref(null)
```

We will implement the following actions:

#### `loadTenantSettings(force = false)`
Fetches both reminder settings and supported timezones. Deduplicates concurrent requests.

```js
async function loadTenantSettings(force = false) {
  if (!force && reminderSettingsLoaded.value && timezonesLoaded.value) {
    return
  }

  if (_settingsPromise.value) {
    return _settingsPromise.value
  }

  _settingsPromise.value = (async () => {
    try {
      const [settingsRes, tzRes] = await Promise.all([
        api.get('/subscription-settings'),
        api.get('/subscription-settings/timezones')
      ])
      reminderSettings.value = settingsRes.data
      timezoneOptions.value = tzRes.data || []
      reminderSettingsLoaded.value = true
      timezonesLoaded.value = true
    } catch (error) {
      // Allow retry by not marking as loaded
      throw error
    } finally {
      _settingsPromise.value = null
    }
  })()

  return _settingsPromise.value
}
```

#### `updateTenantReminderSettings(settingsData)`
Saves updated settings to the database and refreshes the cache inline with the server response.

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
}
```

This helper must be called inside:
- `logout()`
- `switchTenant(tenantId)`
- `exitTenantContext()`

### 2. Dashboard Loading Trigger (`frontend/src/views/TenantDashboardView.vue`)

Integrate settings preload on mount:

```js
onMounted(async () => {
  maybeShowOAuthToastFromQuery()
  await Promise.all([
    loadDashboard(),
    authStore.loadTenantSettings().catch(() => {}) // non-blocking preload
  ])
})
```

### 3. Subscriptions View Orchestration (`frontend/src/views/SubscriptionsView.vue`)

Remove dead and redundant local state:
- Delete `reminderSettings` local ref.
- In `init()`, call `authStore.loadTenantSettings()`.
- Pass properties from `authStore` to the modal component.

```js
// Inside SubscriptionsView.vue init()
async function init() {
  await Promise.all([
    loadClients(),
    loadServices(),
    authStore.loadTenantSettings().catch(() => {})
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
  @saved="loadSubscriptions"
/>
```

### 4. Presentation and Local Mutation (`frontend/src/components/subscriptions/ReminderSettingsModal.vue`)

The modal receives its reactive options and initial values from `authStore` and manages a cloned draft locally.

- Remove the props: `initialSettings`.
- Import `useAuthStore` in `ReminderSettingsModal.vue`.
- Inside `watch(() => props.show)`, deep-clone `authStore.reminderSettings` to local `settings.value`:

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
        // Ensure settings are loaded in memory
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
      }
    }
  }
)
```

Dropdown options read directly from the reactive store properties:
- `timezoneOptions` is read from `authStore.timezoneOptions`.
- Save action delegates to `authStore.updateTenantReminderSettings(settings.value)`:

```js
async function saveSettings() {
  if (loadError.value) return

  isSaving.value = true
  errorMessage.value = ''
  try {
    await authStore.updateTenantReminderSettings(settings.value)
    emit('saved')
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
1. Compile and build the frontend production assets:
   ```bash
   cd frontend && npm run build
   ```
2. Verify that there are no static analyzer or bundler errors related to Pinia store bindings or prop removals.

### Manual Verification Flows
1. **Initial Login/Dashboard Preload**: Login as a tenant. Observe the Network tab in Developer Tools. Ensure exactly one request is sent to `/subscription-settings` and `/subscription-settings/timezones` upon Dashboard mounting.
2. **Subscriptions Route Navigation**: Navigate to "Subscriptions". Ensure NO requests are sent to the settings endpoints since they are already loaded.
3. **Settings Modal Interaction**: Open the "Reminder Settings" modal.
   - Observe that the modal opens instantly with no loaders and NO network calls.
   - Toggle values (e.g. deactivate reminders) and close the modal WITHOUT saving. Ensure that when reopened, the values revert to their original database-backed state.
   - Toggle values and click "Save". Ensure a `PUT` request is sent, the modal closes, and reopening it displays the saved values instantly.
4. **Master Tenant Context Switching**: Log in as Master. Switch context into Tenant A. Open Settings. Save some changes. Switch context into Tenant B. Open Settings. Verify that Tenant B's settings are fetched fresh and do not display cached values from Tenant A.
