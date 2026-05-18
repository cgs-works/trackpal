<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import api from '../services/api'
import { useAuthStore } from '../stores/auth'

const router = useRouter()
const authStore = useAuthStore()

const dashboard = ref(null)
const profile = ref(null)
const passwordForm = ref({
  old_password: '',
  new_password: '',
})
const isLoading = ref(false)
const isSavingPassword = ref(false)
const errorMessage = ref('')
const passwordSuccess = ref('')

const username = computed(() => authStore.username || authStore.user?.username || 'Cliente')
const clientInfo = computed(() => dashboard.value || profile.value || {})
const displayName = computed(() => clientInfo.value.full_name || username.value)

function getApiError(error, fallback) {
  const detail = error.response?.data?.detail
  if (Array.isArray(detail)) {
    return detail.map((item) => item.msg || item.message || String(item)).join(', ')
  }
  return detail || error.response?.data?.message || fallback
}

async function loadDashboard() {
  errorMessage.value = ''
  isLoading.value = true

  try {
    const [dashboardResponse, profileResponse] = await Promise.all([
      api.get('/dashboard'),
      api.get('/me'),
    ])
    dashboard.value = dashboardResponse.data || null
    profile.value = profileResponse.data || null
  } catch (error) {
    errorMessage.value = getApiError(error, 'No se pudo cargar el dashboard.')
  } finally {
    isLoading.value = false
  }
}

async function changePassword() {
  errorMessage.value = ''
  passwordSuccess.value = ''
  isSavingPassword.value = true

  try {
    await api.put('/me/password', passwordForm.value)
    passwordForm.value = {
      old_password: '',
      new_password: '',
    }
    passwordSuccess.value = 'Contraseña actualizada correctamente.'
  } catch (error) {
    errorMessage.value = getApiError(error, 'No se pudo actualizar la contraseña.')
  } finally {
    isSavingPassword.value = false
  }
}

async function handleLogout() {
  await authStore.logout()
  await router.push('/login')
}

onMounted(loadDashboard)
</script>

<template>
  <main class="dashboard-page">
    <header class="dashboard-header">
      <div>
        <p class="eyebrow">Dashboard de cliente</p>
        <h1>Trackpal</h1>
      </div>

      <div class="user-actions">
        <span class="username">{{ username }}</span>
        <button class="button button-secondary" type="button" @click="handleLogout">Cerrar sesión</button>
      </div>
    </header>

    <section v-if="isLoading" class="content-card loading-card" aria-live="polite">
      <span class="spinner" aria-hidden="true"></span>
      <p>Cargando dashboard...</p>
    </section>

    <template v-else>
      <p v-if="errorMessage" class="alert alert-error">{{ errorMessage }}</p>

      <section class="content-card welcome-card">
        <p class="eyebrow">Cliente</p>
        <h2>Bienvenido, {{ displayName }}</h2>
        <p>Solo lectura. Cambia tu contraseña cuando lo necesites.</p>
      </section>

      <section class="content-card profile-card">
        <div class="section-header">
          <div>
            <p class="eyebrow">Datos</p>
            <h2>Tu acceso</h2>
          </div>
        </div>

        <dl class="details-grid">
          <div>
            <dt>UUID</dt>
            <dd>{{ clientInfo.id }}</dd>
          </div>
          <div>
            <dt>Nombre completo</dt>
            <dd>{{ clientInfo.full_name }}</dd>
          </div>
          <div>
            <dt>Login</dt>
            <dd>{{ clientInfo.username }}</dd>
          </div>
          <div>
            <dt>Usuario local</dt>
            <dd>{{ clientInfo.local_username }}</dd>
          </div>
          <div>
            <dt>Teléfono</dt>
            <dd>{{ clientInfo.phone || '—' }}</dd>
          </div>
          <div>
            <dt>Tenant</dt>
            <dd>{{ clientInfo.tenant_name }}</dd>
          </div>
          <div>
            <dt>Prefijo</dt>
            <dd>{{ clientInfo.client_prefix }}</dd>
          </div>
          <div>
            <dt>Estado</dt>
            <dd>{{ clientInfo.is_active ? 'Activo' : 'Inactivo' }}</dd>
          </div>
        </dl>
      </section>

      <section class="content-card profile-card">
        <div class="section-header">
          <div>
            <p class="eyebrow">Seguridad</p>
            <h2>Cambiar contraseña</h2>
          </div>
        </div>

        <p v-if="passwordSuccess" class="alert alert-success">{{ passwordSuccess }}</p>

        <form class="form-grid" @submit.prevent="changePassword">
          <label>
            Contraseña actual
            <input v-model="passwordForm.old_password" type="password" autocomplete="current-password" required />
          </label>

          <label>
            Nueva contraseña
            <input v-model="passwordForm.new_password" type="password" autocomplete="new-password" required />
          </label>

          <div class="form-actions">
            <button class="button button-primary" type="submit" :disabled="isSavingPassword">
              {{ isSavingPassword ? 'Actualizando...' : 'Actualizar contraseña' }}
            </button>
          </div>
        </form>
      </section>
    </template>
  </main>
</template>

<style scoped>
:global(:root) {
  --primary: #4f46e5;
  --success: #22c55e;
  --danger: #ef4444;
  --bg: #f8fafc;
  --card-bg: #ffffff;
  --text: #1e293b;
  --text-secondary: #64748b;
  --border: #e2e8f0;
}

.dashboard-page {
  min-height: 100vh;
  padding: 32px;
  background: var(--bg);
  color: var(--text);
}

.dashboard-header,
.section-header,
.user-actions,
.form-actions,
.loading-card {
  display: flex;
  align-items: center;
}

.dashboard-header,
.section-header {
  justify-content: space-between;
  gap: 16px;
}

.dashboard-header {
  margin-bottom: 24px;
}

.eyebrow {
  margin: 0 0 4px;
  color: var(--text-secondary);
  font-size: 0.85rem;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

h1,
h2,
p {
  margin-top: 0;
}

h1 {
  margin-bottom: 0;
  font-size: 2rem;
}

h2 {
  margin-bottom: 8px;
}

.user-actions {
  gap: 12px;
}

.username {
  color: var(--text-secondary);
  font-weight: 600;
}

.content-card {
  margin-bottom: 24px;
  border: 1px solid var(--border);
  border-radius: 16px;
  padding: 24px;
  background: var(--card-bg);
  box-shadow: 0 10px 25px rgb(15 23 42 / 8%);
}

.welcome-card p:last-child,
.profile-card p:last-child {
  margin-bottom: 0;
}

.details-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
  margin: 18px 0 0;
}

.details-grid div {
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 14px 16px;
  background: #f8fafc;
}

dt {
  color: var(--text-secondary);
  font-size: 0.85rem;
  font-weight: 700;
  text-transform: uppercase;
}

dd {
  margin: 6px 0 0;
  word-break: break-word;
}

.form-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
  margin-top: 18px;
}

label {
  display: grid;
  gap: 8px;
  color: var(--text-secondary);
  font-weight: 700;
}

input {
  width: 100%;
  box-sizing: border-box;
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 11px 12px;
  color: var(--text);
  font: inherit;
}

input:focus {
  border-color: var(--primary);
  outline: 3px solid rgb(79 70 229 / 15%);
}

.form-actions {
  grid-column: 1 / -1;
  justify-content: flex-end;
}

.button {
  cursor: pointer;
  border: 0;
  border-radius: 10px;
  padding: 10px 16px;
  font: inherit;
  font-weight: 700;
}

.button:disabled {
  cursor: not-allowed;
  opacity: 0.7;
}

.button-primary {
  background: var(--primary);
  color: #ffffff;
}

.button-secondary {
  border: 1px solid var(--border);
  background: var(--card-bg);
  color: var(--text);
}

.alert {
  border-radius: 12px;
  padding: 12px 14px;
  font-weight: 700;
}

.alert-error {
  border: 1px solid rgb(239 68 68 / 30%);
  background: rgb(239 68 68 / 10%);
  color: #b91c1c;
}

.alert-success {
  border: 1px solid rgb(34 197 94 / 30%);
  background: rgb(34 197 94 / 10%);
  color: #15803d;
}

.loading-card {
  justify-content: center;
  gap: 12px;
  color: var(--text-secondary);
}

.spinner {
  width: 22px;
  height: 22px;
  border: 3px solid var(--border);
  border-top-color: var(--primary);
  border-radius: 999px;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

@media (max-width: 720px) {
  .dashboard-page {
    padding: 20px;
  }

  .dashboard-header,
  .section-header {
    align-items: flex-start;
    flex-direction: column;
  }

  .details-grid,
  .form-grid {
    grid-template-columns: 1fr;
  }

  .form-actions {
    justify-content: stretch;
  }
}
</style>
