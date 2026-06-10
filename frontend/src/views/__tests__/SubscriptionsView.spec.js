import { describe, it, expect, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { renderWithApp } from '@/test-utils/renderWithApp'
import SubscriptionsView from '../SubscriptionsView.vue'
import api from '@/services/api'

vi.mock('@/services/api', () => ({
  default: {
    get: vi.fn(),
  },
}))

vi.mock('@/stores/auth', () => ({
  useAuthStore: () => ({
    loadTenantSettings: vi.fn().mockResolvedValue(),
  }),
}))

vi.mock('@/stores/i18n', () => ({
  useI18nStore: () => ({ t: key => key }),
}))

describe('SubscriptionsView regressions', () => {
  it('passes the current route client_id into the filter UI', async () => {
    api.get
      .mockResolvedValueOnce({ data: [{ id: 'c1', full_name: 'Client One' }] })
      .mockResolvedValueOnce({ data: [{ id: 's1', name: 'Netflix' }] })
      .mockResolvedValueOnce({ data: [{ id: 'p1', name: 'Basic' }] })
      .mockResolvedValueOnce({ data: [] })

    const wrapper = await renderWithApp(SubscriptionsView, {
      routes: [{ path: '/admin/subscriptions', component: SubscriptionsView }],
      path: '/admin/subscriptions?client_id=c1',
    })

    await flushPromises()
    await wrapper.vm.$nextTick()
    expect(wrapper.get('[data-testid="filter-client"]').element.value).toBe('c1')
  })

  it('opens the reminder settings modal when the button is clicked', async () => {
    api.get
      .mockResolvedValueOnce({ data: [] })
      .mockResolvedValueOnce({ data: [] })
      .mockResolvedValueOnce({ data: [] })

    const wrapper = await renderWithApp(SubscriptionsView)
    await wrapper.get('[data-testid="open-reminder-settings"]').trigger('click')
    // Dialog renders via teleport — check document body for the title
    expect(document.body.textContent).toContain('frontend.subscriptions.reminder_settings_title')
  })
})
