import { ref } from 'vue'

const theme = ref('light')
let isInitialized = false

export function useTheme(forceInit = false) {
  function initTheme() {
    if (isInitialized && !forceInit) return
    isInitialized = true

    if (typeof window === 'undefined') return

    const savedTheme = localStorage.getItem('theme')
    const prefersDark = window.matchMedia?.('(prefers-color-scheme: dark)').matches

    if (savedTheme === 'dark' || (!savedTheme && prefersDark)) {
      theme.value = 'dark'
      document.documentElement.classList.add('dark')
      document.documentElement.style.colorScheme = 'dark'
    } else {
      theme.value = 'light'
      document.documentElement.classList.remove('dark')
      document.documentElement.style.colorScheme = 'light'
    }
  }

  function toggleTheme() {
    if (typeof window === 'undefined') return

    if (theme.value === 'dark') {
      theme.value = 'light'
      localStorage.setItem('theme', 'light')
      document.documentElement.classList.remove('dark')
      document.documentElement.style.colorScheme = 'light'
    } else {
      theme.value = 'dark'
      localStorage.setItem('theme', 'dark')
      document.documentElement.classList.add('dark')
      document.documentElement.style.colorScheme = 'dark'
    }
  }

  // Safe single initialization
  initTheme()

  return {
    theme,
    toggleTheme
  }
}
