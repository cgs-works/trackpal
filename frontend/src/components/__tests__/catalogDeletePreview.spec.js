import { describe, expect, it } from 'vitest'
import { formatCount, formatPreviewRow, isDeleteConfirmationValid } from '../catalogDeletePreview'

describe('catalog delete preview helpers', () => {
  it('accepts CONFIRM and CONFIRMAR case-insensitively', () => {
    expect(isDeleteConfirmationValid('CONFIRM')).toBe(true)
    expect(isDeleteConfirmationValid(' confirmar ')).toBe(true)
    expect(isDeleteConfirmationValid('CONFIRMAR')).toBe(true)
    expect(isDeleteConfirmationValid('confirm')).toBe(true)
    expect(isDeleteConfirmationValid('delete')).toBe(false)
    expect(isDeleteConfirmationValid('')).toBe(false)
    expect(isDeleteConfirmationValid(null)).toBe(false)
  })

  it('formats singular and plural counts through i18n keys', () => {
    const t = (key, params) => `${key}:${params?.count ?? ''}`
    expect(formatCount(t, 1, 'frontend.catalog.plan_one', 'frontend.catalog.plan_other')).toBe('frontend.catalog.plan_one:1')
    expect(formatCount(t, 3, 'frontend.catalog.plan_one', 'frontend.catalog.plan_other')).toBe('frontend.catalog.plan_other:3')
    expect(formatCount(t, 0, 'frontend.catalog.plan_one', 'frontend.catalog.plan_other')).toBe('frontend.catalog.plan_other:0')
  })

  it('formats preview rows without throwing on missing phone', () => {
    const row = formatPreviewRow({
      streaming_email: 'active@example.com',
      client_name: 'Cliente Demo',
      client_phone: null,
      service_name: 'Netflix',
      plan_name: 'Premium',
      expires_at: '2026-07-15T00:00:00Z',
    })
    expect(row).toContain('active@example.com')
    expect(row).toContain('Cliente Demo')
    expect(row).toContain('Netflix/Premium')
    expect(row).toContain('2026-07-15')
  })

  it('formats preview rows with missing name and no expires', () => {
    const row = formatPreviewRow({
      streaming_email: 'another@example.com',
      client_name: null,
      client_phone: '584241234567',
      service_name: 'Disney',
      plan_name: 'Standard',
      expires_at: null,
    })
    expect(row).toContain('another@example.com')
    expect(row).toContain('—')
    expect(row).toContain('584241234567')
    expect(row).toContain('Disney/Standard')
  })
})
