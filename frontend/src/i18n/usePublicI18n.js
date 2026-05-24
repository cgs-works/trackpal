import { ref } from 'vue'
import catalog from './public.json'

const STORAGE_KEY = 'publicLocale'
const DEFAULT_LOCALE = 'en'

function loadFromStorage() {
  try {
    return localStorage.getItem(STORAGE_KEY) || DEFAULT_LOCALE
  } catch {
    return DEFAULT_LOCALE
  }
}

const locale = ref(loadFromStorage())

/**
 * Persist selected locale to localStorage.
 * Reactive update propagates to all components using usePublicI18n().
 */
export function setLocale(value) {
  locale.value = value
  try {
    localStorage.setItem(STORAGE_KEY, value)
  } catch {
    /* localStorage unavailable — keep in-memory only */
  }
}

/**
 * Pre-auth i18n composable.
 *
 * Returns a reactive `locale` ref, a `setLocale` setter that persists
 * to localStorage, and a `t(key, params?)` resolver backed by the local
 * JSON catalog.
 *
 * Default locale is English. Non-EN selection persists across visits.
 *
 * Usage in any unauthenticated view/component:
 *   const { locale, setLocale, t } = usePublicI18n()
 *   <h1>{{ t('login.title') }}</h1>
 *   <select v-model="locale">…
 */
export function usePublicI18n() {
  function t(key, params) {
    const loc = locale.value
    const strings = catalog[loc] || catalog[DEFAULT_LOCALE]
    let template = strings?.[key]
    if (template === undefined) {
      template = catalog[DEFAULT_LOCALE]?.[key]
    }
    if (template === undefined) {
      if (import.meta.env.DEV) {
        console.warn(`[publicI18n] Missing key: ${key}`)
      }
      return key
    }
    if (params) {
      return Object.entries(params).reduce(
        (str, [k, v]) => str.replace(new RegExp(`\\{${k}\\}`, 'g'), String(v)),
        template
      )
    }
    return template
  }

  return { locale, setLocale, t }
}
