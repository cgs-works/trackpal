import { afterEach, describe, it, expect, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { renderWithApp } from '@/test-utils/renderWithApp'
import api from '@/services/api'
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
  afterEach(() => {
    document.body.innerHTML = ''
  })

  it('renders the master overview page shell', async () => {
    const wrapper = await renderWithApp(MasterDashboardView)
    await flushPromises()
    expect(wrapper.text()).toContain('Overview')
  })

  it('renders tenants as a summary-first selectable workspace', async () => {
    api.get.mockResolvedValueOnce({
      data: {
        data: [
          { id: 1, full_name: 'Tenant A', email: 'a@example.com', phone: '111', is_active: true },
          { id: 2, full_name: 'Tenant B', email: 'b@example.com', phone: '222', is_active: false },
        ],
        meta: { total: 2, active: 1, inactive: 1 },
      },
    })

    const wrapper = await renderWithApp(MasterDashboardView, {
      routes: [{ path: '/master/overview', component: MasterDashboardView }],
      path: '/master/overview',
    })
    await flushPromises()

    expect(wrapper.text()).toContain('Total')
    expect(wrapper.text()).toContain('Active')
    expect(wrapper.find('[data-testid="tenant-row-1"]').exists()).toBe(true)

    await wrapper.get('[data-testid="tenant-row-1"]').trigger('click')
    expect(wrapper.find('[data-testid="tenant-inspector"]').exists()).toBe(true)
  })

  it('opens tenant edit dialog from visible row action without selecting the row', async () => {
    api.get.mockResolvedValueOnce({
      data: {
        data: [{ id: 1, full_name: 'Tenant A', email: 'a@example.com', phone: '111', is_active: true }],
        meta: { total: 1, active: 1, inactive: 0 },
      },
    })

    const wrapper = await renderWithApp(MasterDashboardView, {
      routes: [{ path: '/master/overview', component: MasterDashboardView }],
      path: '/master/overview',
    })
    await flushPromises()

    await wrapper.get('[data-testid="tenant-edit-1"]').trigger('click')

    expect(document.body.querySelector('[data-testid="tenant-form-dialog"]')).toBeTruthy()
    expect(wrapper.find('[data-testid="tenant-inspector"]').exists()).toBe(false)
  })

  it('renders the client overview page shell', async () => {
    const wrapper = await renderWithApp(ClientDashboardView)
    await flushPromises()
    expect(wrapper.text()).toContain('frontend.dashboard.client.security')
  })
})
