<script setup>
import { useTheme } from '../composables/useTheme'

const { theme, toggleTheme } = useTheme()
</script>

<template>
  <button
    @click="toggleTheme"
    type="button"
    class="p-2 rounded-md hover:bg-stone-100 dark:hover:bg-zinc-800 text-stone-500 dark:text-zinc-400 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500"
    :title="theme === 'dark' ? 'Cambiar a Modo Claro' : 'Cambiar a Modo Oscuro'"
    aria-label="Toggle Theme"
  >
    <!-- Sun Icon (visible in dark theme) -->
    <svg v-if="theme === 'dark'" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-5 h-5 text-amber-400">
      <path stroke-linecap="round" stroke-linejoin="round" d="M12 3v2.25m0 13.5V21M4.22 4.22l1.625 1.625M16.125 16.125l1.625 1.625M3 12h2.25m13.5 0H21M4.22 19.78l1.625-1.625M16.125 7.875l1.625-1.625M12 7.5a4.5 4.5 0 100 9 4.5 4.5 0 000-9z" />
    </svg>
    <!-- Moon Icon (visible in light theme) -->
    <svg v-else xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-5 h-5 text-stone-500">
      <path stroke-linecap="round" stroke-linejoin="round" d="M21.752 15.002A9.718 9.718 0 0118 15.75c-5.385 0-9.75-4.365-9.75-9.75 0-1.33.266-2.597.748-3.752A9.753 9.753 0 003 11.25C3 16.635 7.365 21 12.75 21a9.753 9.753 0 009.002-5.998z" />
    </svg>
  </button>
</template>
