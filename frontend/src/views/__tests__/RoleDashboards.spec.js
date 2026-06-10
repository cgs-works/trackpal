import { describe, it, expect, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { renderWithApp } from '@/test-utils/renderWithApp'
import MasterDashboardView from '../MasterDashboardView.vue'
import ClientDashboardView from '../ClientDashboardView.vue'

vi.mock('@/services/api', () => ({
  default: {
    get: vi.fn().mockImplementation((url) => {
      if (url === '/dashboard') {
        return Promise.resolve({ data: { id: 'client-1', full_name: 'Client User', username: 'client', is_active: true, tenant_name: 'TestCorp', client_prefix: 'TC', subscriptions: [] } })
      }
      if (url === '/me') {
        return Promise.resolve({ data: { id: 'client-1', full_name: 'Client User', username: 'client', is_active: true, tenant_name: 'TestCorp', client_prefix: 'TC' } })
      }
      return Promise.resolve({ data: { data: [] } })
    }),
    post: vi.fn().mockResolvedValue({ data: {} }),
    put: vi.fn().mockResolvedValue({ data: {} }),
    patch: vi.fn().mockResolvedValue({ data: {} }),
    delete: vi.fn().mockResolvedValue({ data: {} }),
  },
}))

vi.mock('@/stores/auth', () => ({
  useAuthStore: () => ({
    username: 'Master',
    role: 'master',
    isAuthenticated: true,
    activeTenantId: null,
    switchTenant: vi.fn().mockResolvedValue({}),
  }),
}))

vi.mock('@/stores/i18n', () => ({
  useI18nStore: () => ({
    t: (key) => key,
    loadCatalog: vi.fn(),
    locale: 'en',
  }),
}))

vi.mock('@/config/navigation', () => ({
  getNavigationContext: () => ({
    mode: 'master',
    items: [
      { label: 'Overview', to: '/master/overview' },
      { label: 'Code Services', to: '/master/code-services' },
    ],
  }),
}))

describe('role dashboards', () => {
  it('renders the master overview page shell', async () => {
    const wrapper = await renderWithApp(MasterDashboardView)
    await flushPromises()
    expect(wrapper.text()).toContain('Overview')
  })

  it('renders the client overview page shell', async () => {
    const wrapper = await renderWithApp(ClientDashboardView)
    await flushPromises()
    expect(wrapper.text()).toContain('Security')
  })
})
