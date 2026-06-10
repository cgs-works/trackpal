import { describe, it, expect, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { renderWithApp } from '@/test-utils/renderWithApp'
import LoginView from '../LoginView.vue'

vi.mock('@/stores/auth', () => ({
  useAuthStore: () => ({
    login: vi.fn().mockResolvedValue({ user: { role: 'tenant' } }),
  }),
}))

vi.mock('@/stores/i18n', () => ({
  useI18nStore: () => ({ loadCatalog: vi.fn(), t: key => key }),
}))

describe('LoginView', () => {
  it('renders the form and submits to the tenant overview route', async () => {
    const wrapper = await renderWithApp(LoginView, {
      routes: [
        { path: '/login', component: LoginView },
        { path: '/admin/overview', component: { template: '<div>Tenant</div>' } },
      ],
      path: '/login',
    })

    await wrapper.get('#username').setValue('tenant')
    await wrapper.get('#password').setValue('tenant-password')
    await wrapper.get('form').trigger('submit.prevent')
    await flushPromises()

    expect(wrapper.vm.$router.currentRoute.value.path).toBe('/admin/overview')
  })
})
