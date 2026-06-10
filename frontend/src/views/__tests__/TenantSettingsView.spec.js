import { describe, it, expect, vi } from 'vitest'
import { renderWithApp } from '@/test-utils/renderWithApp'
import TenantSettingsView from '../TenantSettingsView.vue'
import api from '@/services/api'

vi.mock('@/services/api', () => ({
  default: {
    get: vi.fn(),
    put: vi.fn(),
  },
}))

vi.mock('@/stores/i18n', () => ({
  useI18nStore: () => ({ t: key => key, loadCatalog: vi.fn() }),
}))

describe('TenantSettingsView', () => {
  it('loads /me and saves profile data', async () => {
    api.get.mockResolvedValueOnce({ data: { full_name: 'Active Tenant', email: 'tenant@example.com', phone: '12015550002', locale: 'en' } })
    api.put.mockResolvedValueOnce({ data: { full_name: 'Updated Tenant', email: 'tenant@example.com', phone: '12015550002', locale: 'es' } })

    const wrapper = await renderWithApp(TenantSettingsView)
    expect(api.get).toHaveBeenCalledWith('/me')
    await wrapper.get('#profile_locale').setValue('es')
    await wrapper.get('form[data-testid="tenant-profile-form"]').trigger('submit.prevent')
    expect(api.put).toHaveBeenCalledWith('/me', expect.objectContaining({ locale: 'es' }))
  })
})
