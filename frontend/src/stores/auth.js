import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import axios from 'axios'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1'

export const useAuthStore = defineStore('auth', () => {
  const token = ref(localStorage.getItem('token'))
  const refreshToken = ref(localStorage.getItem('refreshToken'))
  const user = ref(JSON.parse(localStorage.getItem('user') || 'null'))

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
    return data
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
  }

  return { token, refreshToken, user, isAuthenticated, role, username, login, logout }
})
