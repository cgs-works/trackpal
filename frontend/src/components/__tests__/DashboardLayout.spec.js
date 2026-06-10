import { describe, it, expect } from 'vitest'
import DashboardLayout from '../DashboardLayout.vue'
import { renderWithApp } from '@/test-utils/renderWithApp'
import { useAuthStore } from '@/stores/auth'

describe('DashboardLayout', () => {
  it('shows tenant support navigation when a master has activeTenantId and is on /admin/*', async () => {
    const wrapper = await renderWithApp(DashboardLayout, {
      routes: [{ path: '/admin/clients', component: DashboardLayout }],
      path: '/admin/clients',
      slots: { default: '<div>body</div>' },
    })

    const store = useAuthStore()
    store.user = { role: 'master', username: 'master' }
    store.activeTenantId = 'tenant-1'
    await wrapper.vm.$nextTick()

    expect(wrapper.text()).toContain('Clients')
    expect(wrapper.text()).toContain('Exit support')
  })
})
