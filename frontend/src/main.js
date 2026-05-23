import { createApp } from 'vue'
import { createPinia } from 'pinia'
import './style.css'
import App from './App.vue'
import router from './router'
import { useAuthStore } from './stores/auth'
import { useI18nStore } from './stores/i18n'

const app = createApp(App)

app.use(createPinia())
app.use(router)

// Load i18n catalog on app mount if user already authenticated (page refresh)
const authStore = useAuthStore()
if (authStore.isAuthenticated) {
  useI18nStore().loadCatalog()
}

app.mount('#app')
