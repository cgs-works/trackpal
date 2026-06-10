import { ref, watch } from 'vue'

const theme = ref('light')

export function useTheme() {
  function initTheme() {
    const savedTheme = localStorage.getItem('theme')
    const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches

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

  // Inicialización única
  initTheme()

  return {
    theme,
    toggleTheme
  }
}
