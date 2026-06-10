import { describe, it, expect, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import router from '../index'
import { useAuthStore } from '@/stores/auth'

describe('router', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
  })

  it('redirects legacy tenant dashboard to /admin/overview', async () => {
    const store = useAuthStore()
    store.token = 'token'
    store.user = { role: 'tenant', id: 'tenant-user' }

    await router.push('/admin/dashboard')
    expect(router.currentRoute.value.fullPath).toBe('/admin/overview')
  })

  it('allows master support mode into tenant workflow pages but not /admin/settings', async () => {
    const store = useAuthStore()
    store.token = 'token'
    store.user = { role: 'master', id: 'master-user' }
    store.activeTenantId = 'tenant-1'

    await router.push('/admin/clients')
    expect(router.currentRoute.value.fullPath).toBe('/admin/clients')

    await router.push('/admin/settings')
    expect(router.currentRoute.value.fullPath).not.toBe('/admin/settings')
  })
})
