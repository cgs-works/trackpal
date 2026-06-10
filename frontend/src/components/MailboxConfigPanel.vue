<script setup>
import { computed, ref } from 'vue'
import api from '../services/api'
import { useI18nStore } from '../stores/i18n'
import InlineAlert from './InlineAlert.vue'
import StatusBadge from './StatusBadge.vue'

const i18nStore = useI18nStore()

const emit = defineEmits(['updated'])

const props = defineProps({
  mailbox: { type: Object, default: null },
})

const mailboxError = ref('')
const mailboxSuccess = ref('')
const showImapForm = ref(false)
const isTestingMailbox = ref(false)
const isDisconnectingMailbox = ref(false)
const isSavingImap = ref(false)
const isStartingOAuth = ref(false)

const hasMailbox = computed(() => !!props.mailbox)
const isConnected = computed(() => props.mailbox?.status === 'connected')
const showConnectActions = computed(() => !hasMailbox.value || !isConnected.value)
const imapForm = ref({
  mailbox_email: '',
  imap_host: '',
  imap_port: 993,
  imap_ssl: true,
  imap_password: '',
})

const imapTemplates = {
  gmail: { host: 'imap.gmail.com', port: 993, ssl: true },
  outlook: { host: 'outlook.office365.com', port: 993, ssl: true },
}

function getApiError(error, fallback) {
  const detail = error.response?.data?.detail
  if (Array.isArray(detail)) {
    return detail.map((item) => item.msg || item.message || String(item)).join(', ')
  }
  return detail || error.response?.data?.message || fallback
}

async function saveImapConfig() {
  mailboxError.value = ''
  mailboxSuccess.value = ''
  isSavingImap.value = true
  try {
    await api.put('/tenant/mailbox/', {
      provider: 'imap_custom',
      mailbox_email: imapForm.value.mailbox_email,
      imap_host: imapForm.value.imap_host,
      imap_port: imapForm.value.imap_port,
      imap_ssl: imapForm.value.imap_ssl,
      imap_password: imapForm.value.imap_password,
    })
    mailboxSuccess.value = i18nStore.t('frontend.mailbox.success_saved')
    showImapForm.value = false
    emit('updated')
  } catch (error) {
    mailboxError.value = getApiError(error, i18nStore.t('frontend.mailbox.error_save'))
  } finally {
    isSavingImap.value = false
  }
}

async function testMailbox() {
  mailboxError.value = ''
  mailboxSuccess.value = ''
  isTestingMailbox.value = true
  try {
    const response = await api.post('/tenant/mailbox/test')
    if (response.data.success) {
      mailboxSuccess.value = i18nStore.t('frontend.mailbox.success_test')
    } else {
      mailboxError.value = i18nStore.t('frontend.mailbox.test_failed', { error: response.data.message })
    }
    emit('updated')
  } catch (error) {
    mailboxError.value = getApiError(error, i18nStore.t('frontend.mailbox.error_test'))
  } finally {
    isTestingMailbox.value = false
  }
}

async function startOAuth(provider) {
  mailboxError.value = ''
  mailboxSuccess.value = ''
  isStartingOAuth.value = true
  try {
    const response = await api.post(`/tenant/mailbox/oauth/${provider}/start`)
    const popup = window.open(response.data.auth_url, '_blank', 'noopener,noreferrer')
    if (popup && !popup.closed) {
      mailboxSuccess.value = i18nStore.t('frontend.mailbox.oauth_started')
    } else {
      mailboxError.value = i18nStore.t('frontend.mailbox.error_oauth')
      console.error('OAuth popup blocked or failed to open')
    }
  } catch (error) {
    mailboxError.value = getApiError(error, i18nStore.t('frontend.mailbox.error_oauth'))
  } finally {
    isStartingOAuth.value = false
  }
}

async function disconnectMailbox() {
  mailboxError.value = ''
  mailboxSuccess.value = ''
  isDisconnectingMailbox.value = true
  try {
    await api.post('/tenant/mailbox/disconnect')
    mailboxSuccess.value = i18nStore.t('frontend.mailbox.success_disconnected')
    emit('updated')
  } catch (error) {
    mailboxError.value = getApiError(error, i18nStore.t('frontend.mailbox.error_disconnect'))
  } finally {
    isDisconnectingMailbox.value = false
  }
}

function openImapSetup(templateKey = 'custom') {
  mailboxError.value = ''
  mailboxSuccess.value = ''
  imapForm.value.mailbox_email = props.mailbox?.mailbox_email || ''

  if (templateKey === 'gmail') {
    imapForm.value.imap_host = imapTemplates.gmail.host
    imapForm.value.imap_port = imapTemplates.gmail.port
    imapForm.value.imap_ssl = imapTemplates.gmail.ssl
  } else if (templateKey === 'outlook') {
    imapForm.value.imap_host = imapTemplates.outlook.host
    imapForm.value.imap_port = imapTemplates.outlook.port
    imapForm.value.imap_ssl = imapTemplates.outlook.ssl
  } else {
    imapForm.value.imap_host = props.mailbox?.imap_host || ''
    imapForm.value.imap_port = props.mailbox?.imap_port || 993
    imapForm.value.imap_ssl = props.mailbox?.imap_ssl ?? true
  }

  imapForm.value.imap_password = ''
  showImapForm.value = true
}

function cancelImapSetup() {
  showImapForm.value = false
  imapForm.value = { mailbox_email: '', imap_host: '', imap_port: 993, imap_ssl: true, imap_password: '' }
}

const statusVariant = computed(() => {
  const s = props.mailbox?.status
  if (s === 'connected') return 'active'
  if (s === 'revoked') return 'expired'
  if (s === 'error') return 'cancelled'
  return 'inactive'
})

const providerLabel = computed(() => {
  const p = props.mailbox?.provider
  if (p === 'google') return 'Gmail'
  if (p === 'microsoft') return 'Outlook'
  return 'IMAP'
})

const authMethodLabel = computed(() => {
  return props.mailbox?.auth_method === 'oauth' ? 'OAuth 2.0' : 'IMAP App Password'
})

const statusLabel = computed(() => {
  const s = props.mailbox?.status
  if (s === 'connected') return i18nStore.t('frontend.mailbox.status_connected')
  if (s === 'disconnected') return i18nStore.t('frontend.mailbox.status_disconnected')
  if (s === 'revoked') return i18nStore.t('frontend.mailbox.status_revoked')
  return i18nStore.t('frontend.mailbox.status_error')
})
</script>

<template>
  <section class="max-w-xl">
    <!-- Section heading -->
    <div class="border-b border-stone-100 dark:border-zinc-800/60 pb-3 mb-4">
      <p class="text-xs font-medium text-stone-500 dark:text-zinc-400">{{ i18nStore.t('frontend.mailbox.section_title') }}</p>
      <h2 class="text-sm font-bold text-stone-900 dark:text-zinc-100">{{ i18nStore.t('frontend.mailbox.section_heading') }}</h2>
    </div>

    <!-- Alerts -->
    <InlineAlert v-if="mailboxError" variant="error" :message="mailboxError" />
    <InlineAlert v-if="mailboxSuccess" variant="success" :message="mailboxSuccess" />

    <!-- Not configured placeholder -->
    <p v-if="!mailbox" class="text-xs text-stone-500 dark:text-zinc-400">{{ i18nStore.t('frontend.mailbox.not_configured') }}</p>

    <!-- Connection options when no mailbox or not connected -->
    <template v-if="showConnectActions && !showImapForm">
      <!-- OAuth providers -->
      <div class="border border-stone-200 dark:border-zinc-800 rounded-md p-4 mb-4">
        <h3 class="text-xs font-bold text-stone-900 dark:text-zinc-100 mb-1">{{ i18nStore.t('frontend.mailbox.oauth_title') }}</h3>
        <p class="text-xs text-stone-500 dark:text-zinc-400 mb-1">{{ i18nStore.t('frontend.mailbox.oauth_description') }}</p>
        <p class="text-xs text-stone-400 dark:text-zinc-500 mb-3">{{ i18nStore.t('frontend.mailbox.oauth_note') }}</p>
        <div class="flex flex-wrap gap-2">
          <button
            type="button"
            :disabled="isStartingOAuth"
            class="inline-flex items-center gap-1.5 px-3 py-2 bg-white dark:bg-zinc-950 border border-stone-200 dark:border-zinc-800 rounded-md text-xs font-semibold text-stone-700 dark:text-zinc-300 hover:border-indigo-400 hover:shadow-sm transition-colors cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
            @click="startOAuth('google')"
          >
            <span class="inline-flex items-center justify-center w-5 h-5 rounded bg-stone-100 dark:bg-zinc-800 text-[10px] font-extrabold">G</span>
            {{ i18nStore.t('frontend.mailbox.connect_google') }}
          </button>
          <button
            type="button"
            :disabled="isStartingOAuth"
            class="inline-flex items-center gap-1.5 px-3 py-2 bg-white dark:bg-zinc-950 border border-stone-200 dark:border-zinc-800 rounded-md text-xs font-semibold text-stone-700 dark:text-zinc-300 hover:border-indigo-400 hover:shadow-sm transition-colors cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
            @click="startOAuth('microsoft')"
          >
            <span class="inline-flex items-center justify-center w-5 h-5 rounded bg-stone-100 dark:bg-zinc-800 text-[10px] font-extrabold">M</span>
            {{ i18nStore.t('frontend.mailbox.connect_microsoft') }}
          </button>
        </div>
      </div>

      <!-- IMAP templates -->
      <div class="border border-indigo-300/50 dark:border-indigo-800/50 rounded-md p-4 shadow-sm">
        <h3 class="text-xs font-bold text-stone-900 dark:text-zinc-100 mb-1">{{ i18nStore.t('frontend.mailbox.imap_title') }}</h3>
        <p class="text-xs text-stone-500 dark:text-zinc-400 mb-1">{{ i18nStore.t('frontend.mailbox.imap_description') }}</p>
        <p class="text-xs text-stone-400 dark:text-zinc-500 mb-3">{{ i18nStore.t('frontend.mailbox.imap_note') }}</p>
        <div class="flex flex-wrap gap-2">
          <button
            type="button"
            class="inline-flex items-center gap-1.5 px-3 py-2 bg-white dark:bg-zinc-950 border border-stone-200 dark:border-zinc-800 rounded-md text-xs font-semibold text-stone-700 dark:text-zinc-300 hover:border-indigo-400 hover:shadow-sm transition-colors cursor-pointer"
            @click="openImapSetup('gmail')"
          >
            <span class="inline-flex items-center justify-center w-5 h-5 rounded bg-stone-100 dark:bg-zinc-800 text-[10px] font-extrabold">G</span>
            <div class="flex flex-col items-start gap-0">
              <span>{{ i18nStore.t('frontend.mailbox.template_gmail') }}</span>
              <small class="font-medium text-stone-400 dark:text-zinc-500">{{ i18nStore.t('frontend.mailbox.template_gmail_hint') }}</small>
            </div>
          </button>
          <button
            type="button"
            class="inline-flex items-center gap-1.5 px-3 py-2 bg-white dark:bg-zinc-950 border border-stone-200 dark:border-zinc-800 rounded-md text-xs font-semibold text-stone-700 dark:text-zinc-300 hover:border-indigo-400 hover:shadow-sm transition-colors cursor-pointer"
            @click="openImapSetup('outlook')"
          >
            <span class="inline-flex items-center justify-center w-5 h-5 rounded bg-stone-100 dark:bg-zinc-800 text-[10px] font-extrabold">M</span>
            <div class="flex flex-col items-start gap-0">
              <span>{{ i18nStore.t('frontend.mailbox.template_outlook') }}</span>
              <small class="font-medium text-stone-400 dark:text-zinc-500">{{ i18nStore.t('frontend.mailbox.template_outlook_hint') }}</small>
            </div>
          </button>
          <button
            type="button"
            class="inline-flex items-center gap-1.5 px-3 py-2 bg-white dark:bg-zinc-950 border border-stone-200 dark:border-zinc-800 rounded-md text-xs font-semibold text-stone-700 dark:text-zinc-300 hover:border-indigo-400 hover:shadow-sm transition-colors cursor-pointer"
            @click="openImapSetup('custom')"
          >
            <span class="inline-flex items-center justify-center w-5 h-5 rounded bg-stone-100 dark:bg-zinc-800 text-[10px] font-extrabold">IMAP</span>
            <div class="flex flex-col items-start gap-0">
              <span>{{ i18nStore.t('frontend.mailbox.template_custom') }}</span>
              <small class="font-medium text-stone-400 dark:text-zinc-500">{{ i18nStore.t('frontend.mailbox.template_custom_hint') }}</small>
            </div>
          </button>
        </div>
      </div>
    </template>

    <!-- IMAP configuration form -->
    <form v-if="showImapForm" class="flex flex-col gap-4 mt-4 border border-stone-200 dark:border-zinc-800 rounded-md p-4" @submit.prevent="saveImapConfig">
      <p class="text-xs text-stone-500 dark:text-zinc-400">{{ i18nStore.t('frontend.mailbox.imap_form_help') }}</p>

      <div class="grid grid-cols-2 gap-4">
        <div class="flex flex-col gap-1.5">
          <label for="imap_email" class="text-xs font-medium text-stone-500 dark:text-zinc-400">{{ i18nStore.t('frontend.mailbox.email') }}</label>
          <input id="imap_email" v-model.trim="imapForm.mailbox_email" type="email" required
            class="px-3 py-2 bg-white dark:bg-zinc-950 border border-stone-200 dark:border-zinc-800 rounded-md text-sm text-stone-900 dark:text-zinc-100 focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500">
        </div>
        <div class="flex flex-col gap-1.5">
          <label for="imap_host" class="text-xs font-medium text-stone-500 dark:text-zinc-400">{{ i18nStore.t('frontend.mailbox.imap_host') }}</label>
          <input id="imap_host" v-model.trim="imapForm.imap_host" type="text" required
            class="px-3 py-2 bg-white dark:bg-zinc-950 border border-stone-200 dark:border-zinc-800 rounded-md text-sm text-stone-900 dark:text-zinc-100 focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500">
        </div>
      </div>

      <div class="grid grid-cols-2 gap-4">
        <div class="flex flex-col gap-1.5">
          <label for="imap_port" class="text-xs font-medium text-stone-500 dark:text-zinc-400">{{ i18nStore.t('frontend.mailbox.imap_port') }}</label>
          <input id="imap_port" v-model.number="imapForm.imap_port" type="number" min="1" max="65535" required
            class="px-3 py-2 bg-white dark:bg-zinc-950 border border-stone-200 dark:border-zinc-800 rounded-md text-sm text-stone-900 dark:text-zinc-100 focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500">
        </div>
        <div class="flex flex-col gap-1.5">
          <label for="imap_password" class="text-xs font-medium text-stone-500 dark:text-zinc-400">{{ i18nStore.t('frontend.mailbox.imap_password') }}</label>
          <input id="imap_password" v-model="imapForm.imap_password" type="password" required
            class="px-3 py-2 bg-white dark:bg-zinc-950 border border-stone-200 dark:border-zinc-800 rounded-md text-sm text-stone-900 dark:text-zinc-100 focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500">
        </div>
      </div>

      <label class="flex items-center gap-2 text-xs font-medium text-stone-500 dark:text-zinc-400 cursor-pointer">
        <input v-model="imapForm.imap_ssl" type="checkbox"
          class="rounded border-stone-300 dark:border-zinc-700 text-indigo-600 focus:ring-indigo-500">
        {{ i18nStore.t('frontend.mailbox.imap_ssl') }}
      </label>

      <div class="flex justify-end gap-2">
        <button type="button"
          class="px-3 py-1.5 bg-white dark:bg-zinc-950 border border-stone-200 dark:border-zinc-800 rounded-md text-xs font-semibold text-stone-700 dark:text-zinc-300 hover:bg-stone-50 dark:hover:bg-zinc-900 transition-colors cursor-pointer"
          @click="cancelImapSetup">
          {{ i18nStore.t('frontend.clients.clear') }}
        </button>
        <button type="submit" :disabled="isSavingImap"
          class="px-3 py-1.5 bg-indigo-600 hover:bg-indigo-500 active:bg-indigo-700 disabled:bg-indigo-400 text-white text-xs font-semibold rounded-md shadow-sm transition-colors cursor-pointer disabled:cursor-not-allowed">
          {{ isSavingImap ? i18nStore.t('frontend.mailbox.saving') : i18nStore.t('frontend.mailbox.save_imap') }}
        </button>
      </div>
    </form>

    <!-- Mailbox info when configured -->
    <template v-if="mailbox">
      <div class="flex flex-col gap-3 mt-4">
        <div class="flex items-center gap-2.5">
          <span class="text-xs font-bold text-stone-500 dark:text-zinc-400 min-w-[130px]">{{ i18nStore.t('frontend.mailbox.email') }}</span>
          <span class="text-xs font-semibold text-stone-900 dark:text-zinc-100">{{ mailbox.mailbox_email }}</span>
        </div>
        <div class="flex items-center gap-2.5">
          <span class="text-xs font-bold text-stone-500 dark:text-zinc-400 min-w-[130px]">{{ i18nStore.t('frontend.mailbox.provider') }}</span>
          <span class="text-xs font-semibold text-stone-900 dark:text-zinc-100 capitalize">{{ providerLabel }}</span>
        </div>
        <div class="flex items-center gap-2.5">
          <span class="text-xs font-bold text-stone-500 dark:text-zinc-400 min-w-[130px]">{{ i18nStore.t('frontend.mailbox.method') }}</span>
          <span class="text-xs font-semibold text-stone-900 dark:text-zinc-100">{{ authMethodLabel }}</span>
        </div>
        <div class="flex items-center gap-2.5">
          <span class="text-xs font-bold text-stone-500 dark:text-zinc-400 min-w-[130px]">{{ i18nStore.t('frontend.mailbox.status') }}</span>
          <StatusBadge :variant="statusVariant" :label="statusLabel" />
        </div>
        <div v-if="mailbox.oauth_provider_email" class="flex items-center gap-2.5">
          <span class="text-xs font-bold text-stone-500 dark:text-zinc-400 min-w-[130px]">{{ i18nStore.t('frontend.mailbox.oauth_provider_email') }}</span>
          <span class="text-xs font-semibold text-stone-900 dark:text-zinc-100">{{ mailbox.oauth_provider_email }}</span>
        </div>
        <div v-if="mailbox.imap_host" class="flex items-center gap-2.5">
          <span class="text-xs font-bold text-stone-500 dark:text-zinc-400 min-w-[130px]">{{ i18nStore.t('frontend.mailbox.imap_host') }}</span>
          <span class="text-xs font-semibold text-stone-900 dark:text-zinc-100">{{ mailbox.imap_host }}:{{ mailbox.imap_port }}</span>
        </div>
        <div v-if="mailbox.last_connection_error" class="flex items-center gap-2.5">
          <span class="text-xs font-bold text-stone-500 dark:text-zinc-400 min-w-[130px]">{{ i18nStore.t('frontend.subscriptions.status') }}</span>
          <span class="text-xs font-semibold text-red-600 dark:text-red-400">{{ mailbox.last_connection_error }}</span>
        </div>
      </div>

      <!-- Action buttons -->
      <div class="flex gap-2 mt-5">
        <button
          v-if="mailbox.auth_method !== 'oauth'"
          type="button"
          :disabled="isTestingMailbox"
          class="px-3 py-1.5 bg-white dark:bg-zinc-950 border border-stone-200 dark:border-zinc-800 rounded-md text-xs font-semibold text-stone-700 dark:text-zinc-300 hover:bg-stone-50 dark:hover:bg-zinc-900 transition-colors cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
          @click="testMailbox">
          {{ isTestingMailbox ? i18nStore.t('frontend.mailbox.testing') : i18nStore.t('frontend.mailbox.test') }}
        </button>
        <button
          v-if="showConnectActions"
          type="button"
          class="px-3 py-1.5 bg-white dark:bg-zinc-950 border border-stone-200 dark:border-zinc-800 rounded-md text-xs font-semibold text-stone-700 dark:text-zinc-300 hover:bg-stone-50 dark:hover:bg-zinc-900 transition-colors cursor-pointer"
          @click="openImapSetup('custom')">
          {{ i18nStore.t('frontend.mailbox.setup_imap') }}
        </button>
        <button
          v-if="isConnected"
          type="button"
          :disabled="isDisconnectingMailbox"
          class="px-3 py-1.5 bg-white dark:bg-zinc-950 border border-red-200 dark:border-red-900/50 rounded-md text-xs font-semibold text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-950/20 transition-colors cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
          @click="disconnectMailbox">
          {{ isDisconnectingMailbox ? i18nStore.t('frontend.mailbox.disconnecting') : i18nStore.t('frontend.mailbox.disconnect') }}
        </button>
      </div>
    </template>
  </section>
</template>
