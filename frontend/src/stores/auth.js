import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import axios from 'axios'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1'

export const useAuthStore = defineStore('auth', () => {
  const token = ref(localStorage.getItem('token'))
  const refreshToken = ref(localStorage.getItem('refreshToken'))
  const user = ref(JSON.parse(localStorage.getItem('user') || 'null'))
  const activeTenantId = ref(localStorage.getItem('activeTenantId'))

  const isAuthenticated = computed(() => !!token.value)
  const role = computed(() => user.value?.role || null)
  const username = computed(() => user.value?.username || '')

  async function login(username, password) {
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
    const response = await axios.post(`${API_URL}/auth/switch-tenant`, { tenant_id: tenantId }, {
      headers: { Authorization: `Bearer ${token.value}` }
    })
    setTokenData(response.data)
    return response.data
  }

  async function exitTenantContext() {
    const response = await axios.post(`${API_URL}/auth/switch-tenant`, { tenant_id: null }, {
      headers: { Authorization: `Bearer ${token.value}` }
    })
    setTokenData(response.data)
    return response.data
  }

  async function logout() {
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

  return { token, refreshToken, user, activeTenantId, isAuthenticated, role, username, login, logout, switchTenant, exitTenantContext }
})
