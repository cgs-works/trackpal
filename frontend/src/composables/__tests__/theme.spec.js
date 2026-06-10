import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { useTheme } from '../useTheme'

describe('useTheme', () => {
  beforeEach(() => {
    localStorage.clear()
    document.documentElement.classList.remove('dark')

    // Mock matchMedia defaulting to light
    Object.defineProperty(window, 'matchMedia', {
      writable: true,
      value: vi.fn().mockImplementation((query) => ({
        matches: false,
        media: query,
        onchange: null,
        addListener: vi.fn(),
        removeListener: vi.fn(),
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
        dispatchEvent: vi.fn(),
      })),
    })
  })

  afterEach(() => {
    // Reset the module state so the next test gets a fresh isInitialized
    vi.resetModules()
  })

  it('debe inicializar el tema por defecto (light)', () => {
    const { theme } = useTheme(true)
    expect(theme.value).toBe('light')
  })

  it('debe cambiar de tema correctamente', () => {
    const { theme, toggleTheme } = useTheme(true)
    toggleTheme()
    expect(theme.value).toBe('dark')
    expect(localStorage.getItem('theme')).toBe('dark')
    expect(document.documentElement.classList.contains('dark')).toBe(true)
  })

  it('debe usar prefers-color-scheme: dark como fallback cuando localStorage está vacío', () => {
    // Override matchMedia to report dark mode preference
    window.matchMedia = vi.fn().mockImplementation((query) => ({
      matches: query === '(prefers-color-scheme: dark)',
      media: query,
      onchange: null,
      addListener: vi.fn(),
      removeListener: vi.fn(),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
    }))

    const { theme } = useTheme(true)
    expect(theme.value).toBe('dark')
    expect(document.documentElement.classList.contains('dark')).toBe(true)
  })
})
