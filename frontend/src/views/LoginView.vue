<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const router = useRouter()
const authStore = useAuthStore()

const username = ref('')
const password = ref('')
const errorMessage = ref('')
const isLoading = ref(false)

async function handleSubmit() {
  errorMessage.value = ''
  isLoading.value = true

  try {
    const data = await authStore.login(username.value, password.value)
    const role = data.user?.role

    if (role === 'master') {
      await router.push('/master/dashboard')
    } else if (role === 'tenant') {
      await router.push('/admin/dashboard')
    } else if (role === 'client') {
      await router.push('/client/dashboard')
    } else {
      errorMessage.value = 'Rol de usuario no reconocido'
    }
  } catch (error) {
    errorMessage.value = error.response?.data?.detail || 'No se pudo iniciar sesión'
  } finally {
    isLoading.value = false
  }
}
</script>

<template>
  <main class="login-page">
    <form class="login-form" @submit.prevent="handleSubmit">
      <h1>Iniciar sesión</h1>

      <label for="username">Usuario</label>
      <input
        id="username"
        v-model="username"
        type="text"
        autocomplete="username"
        required
      >

      <label for="password">Contraseña</label>
      <input
        id="password"
        v-model="password"
        type="password"
        autocomplete="current-password"
        required
      >

      <p v-if="errorMessage" class="error-message">{{ errorMessage }}</p>

      <button type="submit" :disabled="isLoading">
        {{ isLoading ? 'Ingresando...' : 'Ingresar' }}
      </button>
    </form>
  </main>
</template>
