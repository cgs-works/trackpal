import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useAuthStore } from '../auth'

// Mock axios before importing the store
vi.mock('axios', () => {
  const mockAxios = {
    post: vi.fn(),
    get: vi.fn(),
    put: vi.fn(),
    create: vi.fn(() => mockAxios),
    interceptors: {
      request: { use: vi.fn() },
      response: { use: vi.fn() },
    },
  }
  return { default: mockAxios }
})

describe('auth store — reminder settings cache', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
  })

  describe('initial cache state', () => {
    it('starts with null/empty cache values', () => {
      const store = useAuthStore()

      expect(store.reminderSettings).toBeNull()
      expect(store.timezoneOptions).toEqual([])
      expect(store.settingsLoaded).toBe(false)
      expect(store.timezonesLoaded).toBe(false)
      expect(store.settingsInFlight).toBeNull()
      expect(store.tenantContextKey).toBeNull()
      expect(store.settingsLoadError).toBeNull()
    })
  })

  describe('_clearTenantSettingsCache', () => {
    it('resets every cache field to its initial value', () => {
      const store = useAuthStore()

      // Set non-default values
      store.reminderSettings = { reminders_enabled: true }
      store.timezoneOptions = [{ value: 'UTC', label: 'UTC' }]
      store.settingsLoaded = true
      store.timezonesLoaded = true
      store.settingsInFlight = Promise.resolve()
      store.tenantContextKey = 'user-42'
      store.settingsLoadError = 'some error'

      store._clearTenantSettingsCache()

      expect(store.reminderSettings).toBeNull()
      expect(store.timezoneOptions).toEqual([])
      expect(store.settingsLoaded).toBe(false)
      expect(store.timezonesLoaded).toBe(false)
      expect(store.settingsInFlight).toBeNull()
      expect(store.tenantContextKey).toBeNull()
      expect(store.settingsLoadError).toBeNull()
    })
  })

  describe('_deriveTenantContextKey', () => {
    it('returns activeTenantId when set (Master in support mode)', () => {
      const store = useAuthStore()
      store.activeTenantId = 'tenant-99'

      const key = store._deriveTenantContextKey()

      expect(key).toBe('tenant-99')
    })

    it('returns user id when activeTenantId is not set (direct tenant session)', () => {
      const store = useAuthStore()
      store.user = { id: 'user-1', username: 'test-tenant' }

      const key = store._deriveTenantContextKey()

      expect(key).toBe('user-1')
    })

    it('returns null when neither tenant id nor user id is available', () => {
      const store = useAuthStore()
      store.activeTenantId = null
      store.user = null

      const key = store._deriveTenantContextKey()

      expect(key).toBeNull()
    })
  })

  describe('cache reset on auth actions', () => {
    it('clears cache before login', async () => {
      const store = useAuthStore()
      // Pre-populate cache
      store.reminderSettings = { reminders_enabled: true }
      store.settingsLoaded = true
      store.tenantContextKey = 'stale-key'

      const axios = await import('axios')
      axios.default.post.mockResolvedValueOnce({
        data: {
          access_token: 'new-token',
          refresh_token: 'new-refresh',
          user: { id: 'user-2', role: 'tenant' },
          active_tenant_id: null,
        },
      })

      await store.login('test', 'pass')

      // Cache should have been cleared before the POST
      expect(store.reminderSettings).toBeNull()
      expect(store.settingsLoaded).toBe(false)
      expect(store.tenantContextKey).toBeNull()
    })

    it('clears cache before logout', async () => {
      const store = useAuthStore()
      store.token = 'some-token'
      store.reminderSettings = { reminders_enabled: true }
      store.settingsLoaded = true
      store.tenantContextKey = 'user-42'

      const axios = await import('axios')
      axios.default.post.mockResolvedValueOnce({ data: {} })

      await store.logout()

      expect(store.reminderSettings).toBeNull()
      expect(store.settingsLoaded).toBe(false)
      expect(store.tenantContextKey).toBeNull()
    })

    it('clears cache before switchTenant', async () => {
      const store = useAuthStore()
      store.token = 'some-token'
      store.reminderSettings = { reminders_enabled: true }
      store.settingsLoaded = true
      store.tenantContextKey = 'tenant-A'

      const axios = await import('axios')
      axios.default.post.mockResolvedValueOnce({
        data: {
          access_token: 'switched-token',
          refresh_token: 'switched-refresh',
          user: { id: 'master-1', role: 'master' },
          active_tenant_id: 'tenant-B',
        },
      })

      await store.switchTenant('tenant-B')

      expect(store.reminderSettings).toBeNull()
      expect(store.settingsLoaded).toBe(false)
      expect(store.tenantContextKey).toBeNull()
    })

    it('clears cache before exitTenantContext', async () => {
      const store = useAuthStore()
      store.token = 'some-token'
      store.reminderSettings = { reminders_enabled: true }
      store.settingsLoaded = true
      store.tenantContextKey = 'tenant-A'

      const axios = await import('axios')
      axios.default.post.mockResolvedValueOnce({
        data: {
          access_token: 'exit-token',
          refresh_token: 'exit-refresh',
          user: { id: 'master-1', role: 'master' },
          active_tenant_id: null,
        },
      })

      await store.exitTenantContext()

      expect(store.reminderSettings).toBeNull()
      expect(store.settingsLoaded).toBe(false)
      expect(store.tenantContextKey).toBeNull()
    })
  })
})
