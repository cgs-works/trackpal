import { describe, it, expect, vi } from 'vitest'
import { renderWithApp } from '@/test-utils/renderWithApp'
import TenantClientsView from '../TenantClientsView.vue'
import TenantCatalogView from '../TenantCatalogView.vue'
import TenantCodeServicesView from '../TenantCodeServicesView.vue'

describe('tenant section routes', () => {
  it('renders the clients page shell', async () => {
    const wrapper = await renderWithApp(TenantClientsView)
    expect(wrapper.text()).toContain('Clients')
  })

  it('renders the catalog page shell', async () => {
    const wrapper = await renderWithApp(TenantCatalogView)
    expect(wrapper.text()).toContain('Catalog')
  })

  it('renders the code services page shell', async () => {
    const wrapper = await renderWithApp(TenantCodeServicesView)
    expect(wrapper.text()).toContain('Code Services')
  })
})
