<script setup>
import { onMounted, ref } from 'vue'
import { useI18nStore } from '@/stores/i18n'
import api from '@/services/api'
import DashboardLayout from '@/components/DashboardLayout.vue'
import PageHeader from '@/components/PageHeader.vue'

const i18nStore = useI18nStore()

// Profile State
const profile = ref({ full_name: '', email: '', phone: '', locale: 'en' })
const passwordForm = ref({ old_password: '', new_password: '' })
const isSavingProfile = ref(false)
const isSavingPassword = ref(false)
const profileSuccess = ref('')
const passwordSuccess = ref('')
const errorMessage = ref('')

async function loadProfile() {
  try {
    const res = await api.get('/me')
    profile.value = {
      full_name: res.data?.full_name || '',
      email: res.data?.email || '',
      phone: res.data?.phone || '',
      locale: res.data?.locale || 'en',
    }
  } catch (err) {
    console.error('Failed to load profile settings', err)
  }
}

async function saveProfile() {
  errorMessage.value = ''
  profileSuccess.value = ''
  passwordSuccess.value = ''
  isSavingProfile.value = true
  try {
    const res = await api.put('/me', profile.value)
    profile.value = {
      full_name: res.data?.full_name || '',
      email: res.data?.email || '',
      phone: res.data?.phone || '',
      locale: res.data?.locale || 'en',
    }
    profileSuccess.value = i18nStore.t('frontend.profile.saved') || 'Profile saved successfully!'
    await i18nStore.loadCatalog()
  } catch (error) {
    errorMessage.value = error.response?.data?.detail || 'Error updating profile'
  } finally {
    isSavingProfile.value = false
  }
}

async function changePassword() {
  errorMessage.value = ''
  profileSuccess.value = ''
  passwordSuccess.value = ''
  isSavingPassword.value = true
  try {
    await api.put('/me/password', passwordForm.value)
    passwordForm.value = { old_password: '', new_password: '' }
    passwordSuccess.value = i18nStore.t('frontend.profile.password_updated') || 'Password updated successfully!'
  } catch (error) {
    errorMessage.value = error.response?.data?.detail || 'Error changing password'
  } finally {
    isSavingPassword.value = false
  }
}

onMounted(() => {
  loadProfile()
})
</script>

<template>
  <DashboardLayout>
    <div class="space-y-6">
      <PageHeader title="Settings" description="Configure account settings." />

      <div v-if="errorMessage" class="text-xs font-medium text-red-500 bg-red-50 dark:bg-red-950/20 border border-red-200/30 dark:border-red-950/40 rounded px-3 py-2">{{ errorMessage }}</div>

      <!-- Profile Configuration -->
      <section class="max-w-xl">
        <div class="border-b border-stone-100 dark:border-zinc-800/60 pb-3 mb-4">
          <h2 class="text-sm font-bold text-stone-900 dark:text-zinc-100">{{ i18nStore.t('frontend.profile.section_heading') || 'Profile Settings' }}</h2>
        </div>
        <div v-if="profileSuccess" class="mb-4 text-xs font-medium text-green-600 bg-green-50 dark:bg-green-950/20 border border-green-200/30 dark:border-green-950/40 rounded px-3 py-2">{{ profileSuccess }}</div>
        <form data-testid="tenant-profile-form" @submit.prevent="saveProfile" class="flex flex-col gap-4">
          <div class="grid grid-cols-2 gap-4">
            <div class="flex flex-col gap-1.5">
              <label for="profile_name" class="font-medium text-stone-500 dark:text-zinc-400">{{ i18nStore.t('frontend.profile.full_name') }}</label>
              <input id="profile_name" v-model="profile.full_name" type="text" autocomplete="name" required class="px-3 py-2 bg-white dark:bg-zinc-950 border border-stone-200 dark:border-zinc-800 rounded-md text-stone-900 dark:text-zinc-100 focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500">
            </div>
            <div class="flex flex-col gap-1.5">
              <label for="profile_email" class="font-medium text-stone-500 dark:text-zinc-400">{{ i18nStore.t('frontend.profile.email') }}</label>
              <input id="profile_email" v-model="profile.email" type="email" autocomplete="email" required class="px-3 py-2 bg-white dark:bg-zinc-950 border border-stone-200 dark:border-zinc-800 rounded-md text-stone-900 dark:text-zinc-100 focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500">
            </div>
          </div>
          <div class="grid grid-cols-2 gap-4">
            <div class="flex flex-col gap-1.5">
              <label for="profile_phone" class="font-medium text-stone-500 dark:text-zinc-400">{{ i18nStore.t('frontend.profile.phone') }}</label>
              <input id="profile_phone" v-model="profile.phone" type="tel" autocomplete="tel" class="px-3 py-2 bg-white dark:bg-zinc-950 border border-stone-200 dark:border-zinc-800 rounded-md text-stone-900 dark:text-zinc-100 focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500">
            </div>
            <div class="flex flex-col gap-1.5">
              <label for="profile_locale" class="font-medium text-stone-500 dark:text-zinc-400">{{ i18nStore.t('frontend.profile.locale') }}</label>
              <select id="profile_locale" v-model="profile.locale" class="px-3 py-2 bg-white dark:bg-zinc-950 border border-stone-200 dark:border-zinc-800 rounded-md text-stone-900 dark:text-zinc-100 focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 cursor-pointer">
                <option value="en">English</option>
                <option value="es">Español</option>
              </select>
            </div>
          </div>
          <div class="flex justify-end">
            <button type="submit" :disabled="isSavingProfile" class="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 active:bg-indigo-700 disabled:bg-indigo-400 text-white font-semibold rounded-md shadow-sm transition-colors cursor-pointer">
              {{ isSavingProfile ? i18nStore.t('frontend.profile.saving') : i18nStore.t('frontend.profile.save') }}
            </button>
          </div>
        </form>
      </section>

      <!-- Change Password -->
      <section class="max-w-xl pt-4 border-t border-stone-100 dark:border-zinc-800/60">
        <div class="pb-3 mb-4">
          <h2 class="text-sm font-bold text-stone-900 dark:text-zinc-100">{{ i18nStore.t('frontend.dashboard.client.change_password') || 'Change Password' }}</h2>
        </div>
        <div v-if="passwordSuccess" class="mb-4 text-xs font-medium text-green-600 bg-green-50 dark:bg-green-950/20 border border-green-200/30 dark:border-green-950/40 rounded px-3 py-2">{{ passwordSuccess }}</div>
        <form @submit.prevent="changePassword" class="flex flex-col gap-4">
          <div class="grid grid-cols-2 gap-4">
            <div class="flex flex-col gap-1.5">
              <label for="current_pw" class="font-medium text-stone-500 dark:text-zinc-400">{{ i18nStore.t('frontend.dashboard.client.current_password') }}</label>
              <input id="current_pw" v-model="passwordForm.old_password" type="password" autocomplete="current-password" required class="px-3 py-2 bg-white dark:bg-zinc-950 border border-stone-200 dark:border-zinc-800 rounded-md text-stone-900 dark:text-zinc-100 focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500">
            </div>
            <div class="flex flex-col gap-1.5">
              <label for="new_pw" class="font-medium text-stone-500 dark:text-zinc-400">{{ i18nStore.t('frontend.dashboard.client.new_password') }}</label>
              <input id="new_pw" v-model="passwordForm.new_password" type="password" autocomplete="new-password" required class="px-3 py-2 bg-white dark:bg-zinc-950 border border-stone-200 dark:border-zinc-800 rounded-md text-stone-900 dark:text-zinc-100 focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500">
            </div>
          </div>
          <div class="flex justify-end">
            <button type="submit" :disabled="isSavingPassword" class="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 active:bg-indigo-700 disabled:bg-indigo-400 text-white font-semibold rounded-md shadow-sm transition-colors cursor-pointer">
              {{ isSavingPassword ? i18nStore.t('frontend.dashboard.client.updating') : i18nStore.t('frontend.dashboard.client.update_password') }}
            </button>
          </div>
        </form>
      </section>
    </div>
  </DashboardLayout>
</template>
