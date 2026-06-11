import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import api from '../services/api'

export const useI18nStore = defineStore('i18n', () => {
  const locale = ref('en')
  const strings = ref({})
  const isLoaded = ref(false)

  async function loadCatalog() {
    try {
      const response = await api.get('/i18n/catalog')
      const data = response.data
      locale.value = data.locale || 'en'
      strings.value = data.catalog || {}
      isLoaded.value = true
    } catch (error) {
      // Fallback: keep previous state or empty
      isLoaded.value = true
    }
  }

  function t(key, params) {
    let template = strings.value[key]
    if (template === undefined) {
      if (import.meta.env.DEV) {
        console.warn(`[i18n] Missing key: ${key}`)
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

  return { locale, strings, isLoaded, loadCatalog, t }
})
