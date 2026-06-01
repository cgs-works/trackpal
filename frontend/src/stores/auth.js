import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import axios from 'axios'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1'

export const useAuthStore = defineStore('auth', () => {
  const token = ref(localStorage.getItem('token'))
  const refreshToken = ref(localStorage.getItem('refreshToken'))
  const user = ref(JSON.parse(localStorage.getItem('user') || 'null'))
  const activeTenantId = ref(localStorage.getItem('activeTenantId'))

  // --- Reminder Settings Cache (runtime-only, Tenant Context bundle) ---
  const reminderSettings = ref(null)
  const timezoneOptions = ref([])
  const settingsLoaded = ref(false)
  const timezonesLoaded = ref(false)
  const settingsInFlight = ref(null)
  const tenantContextKey = ref(null)
  const settingsLoadError = ref(null)

  function _clearTenantSettingsCache() {
    reminderSettings.value = null
    timezoneOptions.value = []
    settingsLoaded.value = false
    timezonesLoaded.value = false
    settingsInFlight.value = null
    tenantContextKey.value = null
    settingsLoadError.value = null
  }

  function _deriveTenantContextKey() {
    // Master in support mode -> tenant id; otherwise -> current user id
    return activeTenantId.value || user.value?.id || null
  }

  // --- end cache ---

  const isAuthenticated = computed(() => !!token.value)
  const role = computed(() => user.value?.role || null)
  const username = computed(() => user.value?.username || '')

  async function login(username, password) {
    _clearTenantSettingsCache()
    const response = await axios.post(`${API_URL}/auth/login`, { username, password })
    const data = response.data
    token.value = data.access_token
    refreshToken.value = data.refresh_token
    user.value = data.user
    localStorage.setItem('token', data.access_token)
    localStorage.setItem('refreshToken', data.refresh_token)
    localStorage.setItem('user', JSON.stringify(data.user))
    activeTenantId.value = data.active_tenant_id || null
    if (activeTenantId.value) localStorage.setItem('activeTenantId', activeTenantId.value)
    else localStorage.removeItem('activeTenantId')
    return data
  }

  function setTokenData(data) {
    token.value = data.access_token
    refreshToken.value = data.refresh_token
    user.value = data.user
    activeTenantId.value = data.active_tenant_id || null
    localStorage.setItem('token', data.access_token)
    localStorage.setItem('refreshToken', data.refresh_token)
    localStorage.setItem('user', JSON.stringify(data.user))
    if (activeTenantId.value) localStorage.setItem('activeTenantId', activeTenantId.value)
    else localStorage.removeItem('activeTenantId')
  }

  async function switchTenant(tenantId) {
    _clearTenantSettingsCache()
    const response = await axios.post(`${API_URL}/auth/switch-tenant`, { tenant_id: tenantId }, {
      headers: { Authorization: `Bearer ${token.value}` }
    })
    setTokenData(response.data)
    return response.data
  }

  async function exitTenantContext() {
    _clearTenantSettingsCache()
    const response = await axios.post(`${API_URL}/auth/switch-tenant`, { tenant_id: null }, {
      headers: { Authorization: `Bearer ${token.value}` }
    })
    setTokenData(response.data)
    return response.data
  }

  async function logout() {
    _clearTenantSettingsCache()
    try {
      await axios.post(`${API_URL}/auth/logout`, { refresh_token: refreshToken.value }, {
        headers: { Authorization: `Bearer ${token.value}` }
      })
    } catch (e) {
      // Ignore errors on logout
    }
    token.value = null
    refreshToken.value = null
    user.value = null
    localStorage.removeItem('token')
    localStorage.removeItem('refreshToken')
    localStorage.removeItem('user')
    activeTenantId.value = null
    localStorage.removeItem('activeTenantId')
  }

  return {
    token, refreshToken, user, activeTenantId,
    isAuthenticated, role, username,
    // Cache state
    reminderSettings, timezoneOptions,
    settingsLoaded, timezonesLoaded,
    settingsInFlight, tenantContextKey, settingsLoadError,
    // Auth actions
    login, logout, switchTenant, exitTenantContext,
    // Cache helpers (internal, exposed for testing)
    _clearTenantSettingsCache, _deriveTenantContextKey,
  }
})
