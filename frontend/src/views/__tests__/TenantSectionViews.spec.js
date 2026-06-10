import { afterEach, describe, it, expect, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { renderWithApp } from '@/test-utils/renderWithApp'
import api from '@/services/api'
import TenantClientsView from '../TenantClientsView.vue'
import TenantCatalogView from '../TenantCatalogView.vue'
import TenantCodeServicesView from '../TenantCodeServicesView.vue'

vi.mock('@/services/api', () => ({
  default: {
    get: vi.fn().mockResolvedValue({ data: [] }),
    post: vi.fn().mockResolvedValue({ data: {} }),
    put: vi.fn().mockResolvedValue({ data: {} }),
    patch: vi.fn().mockResolvedValue({ data: {} }),
    delete: vi.fn().mockResolvedValue({ data: {} }),
  },
}))

vi.mock('@/stores/i18n', () => ({
  useI18nStore: () => ({
    t: (key, params) => (params?.login ? `${key}:${params.login}` : key),
    loadCatalog: vi.fn(),
    locale: 'en',
  }),
}))

vi.mock('@/stores/auth', () => ({
  useAuthStore: () => ({
    username: 'Tenant',
    role: 'tenant',
    isAuthenticated: true,
    activeTenantId: null,
    logout: vi.fn().mockResolvedValue({}),
  }),
}))

describe('tenant section routes', () => {
  afterEach(() => {
    document.body.innerHTML = ''
    vi.clearAllMocks()
  })

  it('renders the clients page shell', async () => {
    const wrapper = await renderWithApp(TenantClientsView)
    expect(wrapper.text()).toContain('Clients')
  })

  it('renders clients with visible actions, dialog editing, and inspector selection', async () => {
    api.get.mockResolvedValueOnce({
      data: [
        { id: 10, full_name: 'Client A', username: 'clienta', local_username: 'clienta', phone: '555', is_active: true },
      ],
    })

    const wrapper = await renderWithApp(TenantClientsView, {
      routes: [{ path: '/admin/clients', component: TenantClientsView }],
      path: '/admin/clients',
    })
    await flushPromises()

    expect(wrapper.find('[data-testid="client-row-10"]').exists()).toBe(true)

    await wrapper.get('[data-testid="client-row-10"]').trigger('click')
    expect(wrapper.find('[data-testid="client-inspector"]').exists()).toBe(true)

    await wrapper.get('[data-testid="client-edit-10"]').trigger('click')
    expect(document.body.querySelector('[data-testid="client-form-dialog"]')).toBeTruthy()
  })

  it('renders the catalog page shell', async () => {
    const wrapper = await renderWithApp(TenantCatalogView)
    expect(wrapper.text()).toContain('Catalog')
  })

  it('keeps catalog service and plan actions visible with typed delete preview', async () => {
    api.get
      .mockResolvedValueOnce({
        data: [
          { id: 1, name: 'Netflix', description: 'Streaming' },
        ],
      })
      .mockResolvedValueOnce({
        data: [{ id: 2, name: 'Premium', duration_days: 30, price: 10 }],
      })
      .mockResolvedValueOnce({
        data: {
          target_type: 'service',
          target_name: 'Netflix',
          affected_plan_count: 1,
          active_subscription_count: 2,
          historical_subscription_count: 3,
          total_subscription_count: 5,
          active_subscriptions: [],
          pagination: { total_pages: 1, has_next: false },
        },
      })

    const wrapper = await renderWithApp(TenantCatalogView, {
      routes: [{ path: '/admin/catalog', component: TenantCatalogView }],
      path: '/admin/catalog',
    })
    await flushPromises()

    expect(wrapper.find('[data-testid="service-edit-1"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="service-delete-1"]').exists()).toBe(true)

    await wrapper.get('[data-testid="service-delete-1"]').trigger('click')
    await flushPromises()

    expect(document.body.textContent).toContain('Netflix')
    expect(document.body.querySelector('[data-testid="catalog-delete-confirm-input"]')).toBeTruthy()
  })

  it('renders the code services page shell', async () => {
    const wrapper = await renderWithApp(TenantCodeServicesView)
    expect(wrapper.text()).toContain('Code Services')
  })
})
