import { afterEach, describe, it, expect, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { renderWithApp } from '@/test-utils/renderWithApp'
import TenantMailboxView from '../TenantMailboxView.vue'
import api from '@/services/api'

vi.mock('@/services/api', () => ({
  default: {
    get: vi.fn(),
  },
}))

describe('TenantMailboxView', () => {
  afterEach(() => {
    vi.clearAllMocks()
  })

  it('treats mailbox 404 as an empty configuration state', async () => {
    api.get.mockRejectedValueOnce({ response: { status: 404, data: { detail: 'Not found' } } })

    const wrapper = await renderWithApp(TenantMailboxView, {
      routes: [{ path: '/admin/mailbox', component: TenantMailboxView }],
      path: '/admin/mailbox',
    })
    await flushPromises()

    expect(wrapper.text()).not.toContain('Not found')
    expect(wrapper.find('[data-testid="mailbox-empty-state"]').exists()).toBe(true)
  })

  it('shows OAuth success feedback from query params', async () => {
    api.get.mockResolvedValueOnce({ data: null })

    const wrapper = await renderWithApp(TenantMailboxView, {
      routes: [{ path: '/admin/mailbox', component: TenantMailboxView }],
      path: '/admin/mailbox?mailbox_oauth=success',
    })
    await flushPromises()

    expect(wrapper.text()).toContain('OAuth')
  })

  it('loads mailbox config and refreshes it after the panel emits updated', async () => {
    api.get
      .mockResolvedValueOnce({ data: { mailbox_email: 'ops@example.com', provider: 'google', auth_method: 'oauth', status: 'connected' } })
      .mockResolvedValueOnce({ data: { mailbox_email: 'ops@example.com', provider: 'google', auth_method: 'oauth', status: 'revoked' } })

    const wrapper = await renderWithApp(TenantMailboxView)
    expect(api.get).toHaveBeenCalledWith('/tenant/mailbox/')

    wrapper.getComponent({ name: 'MailboxConfigPanel' }).vm.$emit('updated')
    await Promise.resolve()

    expect(api.get).toHaveBeenCalledTimes(2)
  })
})
