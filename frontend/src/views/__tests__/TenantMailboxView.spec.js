import { describe, it, expect, vi } from 'vitest'
import { renderWithApp } from '@/test-utils/renderWithApp'
import TenantMailboxView from '../TenantMailboxView.vue'
import api from '@/services/api'

vi.mock('@/services/api', () => ({
  default: {
    get: vi.fn(),
  },
}))

describe('TenantMailboxView', () => {
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
