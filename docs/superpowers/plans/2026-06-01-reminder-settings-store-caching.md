# Reminder Settings Caching in AuthStore Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Cache subscription reminder settings and timezone options in the global Pinia `useAuthStore` to eliminate duplicate network requests when opening/closing the "Reminder Settings" modal.

**Architecture:** Extend Pinia state with reactive cache variables and a request deduplication promise tracker (`_settingsPromise`). Trigger preloading at Dashboard and Subscriptions view levels. Refactor the modal to read from cached state and edit via a cloned draft to prevent premature global store mutation.

**Tech Stack:** Vue 3 SPA, Pinia Store, Axios Client

---

## File Structure & Proposed Changes

| Target File | Change Type | Responsibility |
|---|---|---|
| `frontend/src/stores/auth.js` | Modify | Add `reminderSettings`, `timezoneOptions` cache states, load/update actions, and clear actions. Integrate clearing into authentication lifecycle. |
| `frontend/src/views/TenantDashboardView.vue` | Modify | Trigger non-blocking preload of tenant settings on mount. |
| `frontend/src/views/SubscriptionsView.vue` | Modify | Trigger non-blocking preload in `init()`, remove redundant local ref, pass store-backed values to modal. |
| `frontend/src/components/subscriptions/ReminderSettingsModal.vue` | Modify | Refactor to consume store state, implement local deep copy clone on open, delegate save action to store. |

---

## Tasks

### Task 1: Extend Pinia AuthStore with Caching

**Files:**
- Modify: `frontend/src/stores/auth.js`

- [ ] **Step 1: Define new cache states and promise tracker**

Modify `frontend/src/stores/auth.js` to add the following state refs:

```js
  const reminderSettings = ref(null)
  const timezoneOptions = ref([])
  const reminderSettingsLoaded = ref(false)
  const timezonesLoaded = ref(false)
  const _settingsPromise = ref(null)
```

- [ ] **Step 2: Implement loadTenantSettings action with promise deduplication**

Add the `loadTenantSettings` action to the store:

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
          axios.get(`${API_URL}/subscription-settings`, {
            headers: { Authorization: `Bearer ${token.value}` }
          }),
          axios.get(`${API_URL}/subscription-settings/timezones`, {
            headers: { Authorization: `Bearer ${token.value}` }
          })
        ])
        reminderSettings.value = settingsRes.data
        timezoneOptions.value = tzRes.data || []
        reminderSettingsLoaded.value = true
        timezonesLoaded.value = true
      } catch (error) {
        throw error
      } finally {
        _settingsPromise.value = null
      }
    })()

    return _settingsPromise.value
  }
```

- [ ] **Step 3: Implement updateTenantReminderSettings action**

Add the update action to the store:

```js
  async function updateTenantReminderSettings(settingsData) {
    const response = await axios.put(`${API_URL}/subscription-settings`, settingsData, {
      headers: { Authorization: `Bearer ${token.value}` }
    })
    reminderSettings.value = response.data
    reminderSettingsLoaded.value = true
    return response.data
  }
```

- [ ] **Step 4: Implement clearTenantSettings action**

Add the clear helper and return everything from the store function:

```js
  function clearTenantSettings() {
    reminderSettings.value = null
    timezoneOptions.value = []
    reminderSettingsLoaded.value = false
    timezonesLoaded.value = false
    _settingsPromise.value = null
  }
```

- [ ] **Step 5: Integrate clearTenantSettings into auth lifecycle**

Inside `frontend/src/stores/auth.js`, update `logout`, `switchTenant`, and `exitTenantContext` to call `clearTenantSettings()` at their start:

```js
  async function switchTenant(tenantId) {
    clearTenantSettings()
    const response = await axios.post(`${API_URL}/auth/switch-tenant`, { tenant_id: tenantId }, {
      headers: { Authorization: `Bearer ${token.value}` }
    })
    ...
  }

  async function exitTenantContext() {
    clearTenantSettings()
    const response = await axios.post(`${API_URL}/auth/switch-tenant`, { tenant_id: null }, {
      headers: { Authorization: `Bearer ${token.value}` }
    })
    ...
  }

  async function logout() {
    clearTenantSettings()
    try {
      await axios.post(`${API_URL}/auth/logout`, { refresh_token: refreshToken.value }, {
        headers: { Authorization: `Bearer ${token.value}` }
      })
    ...
  }
```

Make sure to export `reminderSettings`, `timezoneOptions`, `reminderSettingsLoaded`, `timezonesLoaded`, `loadTenantSettings`, `updateTenantReminderSettings`, and `clearTenantSettings` in the returned store object.

- [ ] **Step 6: Verify linter / compiler**

Run: `cd frontend && npm run build` (or check console for syntax bugs).
Expected: Clean compilation, no syntax errors.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/stores/auth.js
git commit -m "feat(store): add tenant settings caching and promise deduplication to authStore"
```


### Task 2: Trigger Preloading at Dashboard & Subscriptions level

**Files:**
- Modify: `frontend/src/views/TenantDashboardView.vue`
- Modify: `frontend/src/views/SubscriptionsView.vue`

- [ ] **Step 1: Update TenantDashboardView.vue to preload on mount**

Modify `frontend/src/views/TenantDashboardView.vue` so that `onMounted` triggers `loadTenantSettings` concurrently with `loadDashboard`:

```js
onMounted(async () => {
  maybeShowOAuthToastFromQuery()
  await Promise.all([
    loadDashboard(),
    authStore.loadTenantSettings().catch(() => {})
  ])
})
```

- [ ] **Step 2: Update SubscriptionsView.vue to preload on init**

Modify `frontend/src/views/SubscriptionsView.vue` to call `authStore.loadTenantSettings()` inside `init()` concurrently:

```js
async function init() {
  await Promise.all([
    loadClients(),
    loadServices(),
    authStore.loadTenantSettings().catch(() => {})
  ])
  await buildPlanMap()

  // Pre-set client_id from route query
  if (route.query.client_id) {
    filters.value.client_id = route.query.client_id
  }

  await loadSubscriptions()
}
```

- [ ] **Step 3: Remove redundant local state in SubscriptionsView.vue**

Remove the local `reminderSettings` ref at lines 33-39 (approx):
```js
// DELETE THIS BLOCK:
const reminderSettings = ref({
  reminders_enabled: false,
  timezone: 'UTC',
  warning_days: [7, 3, 1],
  reminder_time: '09:00',
  recipient_mode: 'tenant_only',
})
```

In the `<ReminderSettingsModal>` tag inside `SubscriptionsView.vue`, remove `:initial-settings="reminderSettings"` binding:

```html
    <ReminderSettingsModal
      :show="showReminderSettings"
      @close="closeModals"
      @saved="loadSubscriptions"
    />
```

- [ ] **Step 4: Verify frontend build**

Run: `cd frontend && npm run build`
Expected: Success with no reference or props errors.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/views/TenantDashboardView.vue frontend/src/views/SubscriptionsView.vue
git commit -m "feat(views): integrate tenant settings preloading and clean up subscriptions view"
```


### Task 3: Refactor ReminderSettingsModal to Consume Cached Store

**Files:**
- Modify: `frontend/src/components/subscriptions/ReminderSettingsModal.vue`

- [ ] **Step 1: Import AuthStore and remove obsolete props/loaders**

Open `frontend/src/components/subscriptions/ReminderSettingsModal.vue`.
1. Import `useAuthStore`:
   ```js
   import { useAuthStore } from '../../stores/auth'
   const authStore = useAuthStore()
   ```
2. Remove `initialSettings` prop from `defineProps`:
   ```js
   const props = defineProps({
     show: { type: Boolean, default: false },
   })
   ```
3. Remove the local `loadSettings` and `loadTimezones` functions completely (lines 52-80).
4. Remove `tzLoadingError` and `loadError` reactive refs if they are no longer needed, or keep them to capture any unexpected initial load errors.

- [ ] **Step 2: Update Watch trigger to clone cached settings**

Rewrite the `watch(() => props.show)` block to load from store and clone into the local `settings` copy:

```js
watch(
  () => props.show,
  async (newVal) => {
    if (newVal) {
      errorMessage.value = ''
      loadError.value = ''
      customDay.value = ''
      
      try {
        // Fallback safety to ensure settings are loaded in memory
        await authStore.loadTenantSettings()
        
        // Deep copy the cached settings to local settings draft
        if (authStore.reminderSettings) {
          settings.value = {
            reminders_enabled: authStore.reminderSettings.reminders_enabled ?? false,
            timezone: authStore.reminderSettings.timezone || 'UTC',
            warning_days: [...(authStore.reminderSettings.warning_days || [7, 3, 1])],
            reminder_time: authStore.reminderSettings.reminder_time || '09:00',
            recipient_mode: authStore.reminderSettings.recipient_mode || 'tenant_only',
          }
        }
      } catch (error) {
        loadError.value = getApiError(error, i18nStore.t('frontend.subscriptions.error_load_settings'))
      }
    }
  }
)
```

- [ ] **Step 3: Connect UI elements to store timezones**

Update the template to map over `authStore.timezoneOptions` instead of `timezoneOptions`:

```html
              <option v-if="!authStore.timezoneOptions.length" value="UTC">UTC</option>
              <option v-for="tz in authStore.timezoneOptions" :key="tz.value" :value="tz.value">{{ tz.label }}</option>
```

- [ ] **Step 4: Update saveSettings action**

Delegate the save action to `authStore.updateTenantReminderSettings` instead of doing local axios calls:

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

- [ ] **Step 5: Run final production build**

Run: `cd frontend && npm run build`
Expected: Clean build, 0 errors.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/subscriptions/ReminderSettingsModal.vue
git commit -m "refactor(modal): convert ReminderSettingsModal to consume authStore cache"
```
