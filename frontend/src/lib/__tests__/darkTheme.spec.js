import { beforeEach, describe, expect, it } from 'vitest'
import { applyDarkTheme } from '@/lib/darkTheme'

describe('applyDarkTheme', () => {
  beforeEach(() => {
    document.documentElement.className = ''
  })

  it('forces the document into dark mode', () => {
    applyDarkTheme()

    expect(document.documentElement.classList.contains('dark')).toBe(true)
  })

  it('is safe to call more than once', () => {
    applyDarkTheme()
    applyDarkTheme()

    expect(document.documentElement.classList.contains('dark')).toBe(true)
  })
})
