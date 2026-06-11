<script setup>
import { computed, ref } from 'vue'
import api from '../services/api'
import { useI18nStore } from '../stores/i18n'

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
</script>

<template>
  <section class="content-card mailbox-card">
    <div class="section-header">
      <div>
        <p class="eyebrow">{{ i18nStore.t('frontend.mailbox.section_title') }}</p>
        <h2>{{ i18nStore.t('frontend.mailbox.section_heading') }}</h2>
      </div>
    </div>

    <p v-if="mailboxError" class="alert alert-error">{{ mailboxError }}</p>
    <p v-if="mailboxSuccess" class="alert alert-success">{{ mailboxSuccess }}</p>

    <p v-if="!mailbox" class="placeholder-message">{{ i18nStore.t('frontend.mailbox.not_configured') }}</p>

    <template v-if="showConnectActions && !showImapForm">
      <div class="connection-sections">
        <div class="connection-card">
          <h3>{{ i18nStore.t('frontend.mailbox.oauth_title') }}</h3>
          <p>{{ i18nStore.t('frontend.mailbox.oauth_description') }}</p>
          <p class="helper-note">{{ i18nStore.t('frontend.mailbox.oauth_note') }}</p>
          <div class="provider-grid">
            <button class="provider-btn" type="button" :disabled="isStartingOAuth" @click="startOAuth('google')">
              <span class="provider-icon">G</span>
              {{ i18nStore.t('frontend.mailbox.connect_google') }}
            </button>
            <button class="provider-btn" type="button" :disabled="isStartingOAuth" @click="startOAuth('microsoft')">
              <span class="provider-icon">M</span>
              {{ i18nStore.t('frontend.mailbox.connect_microsoft') }}
            </button>
          </div>
        </div>

        <div class="connection-card recommended-card">
          <h3>{{ i18nStore.t('frontend.mailbox.imap_title') }}</h3>
          <p>{{ i18nStore.t('frontend.mailbox.imap_description') }}</p>
          <p class="helper-note">{{ i18nStore.t('frontend.mailbox.imap_note') }}</p>
          <div class="provider-grid">
            <button class="provider-btn" type="button" @click="openImapSetup('gmail')">
              <span class="provider-icon">G</span>
              {{ i18nStore.t('frontend.mailbox.template_gmail') }}
              <small>{{ i18nStore.t('frontend.mailbox.template_gmail_hint') }}</small>
            </button>
            <button class="provider-btn" type="button" @click="openImapSetup('outlook')">
              <span class="provider-icon">M</span>
              {{ i18nStore.t('frontend.mailbox.template_outlook') }}
              <small>{{ i18nStore.t('frontend.mailbox.template_outlook_hint') }}</small>
            </button>
            <button class="provider-btn" type="button" @click="openImapSetup('custom')">
              <span class="provider-icon">IMAP</span>
              {{ i18nStore.t('frontend.mailbox.template_custom') }}
              <small>{{ i18nStore.t('frontend.mailbox.template_custom_hint') }}</small>
            </button>
          </div>
        </div>
      </div>
    </template>

    <form v-if="showImapForm" class="form-grid" @submit.prevent="saveImapConfig">
      <p class="form-guidance">{{ i18nStore.t('frontend.mailbox.imap_form_help') }}</p>
      <label>
        {{ i18nStore.t('frontend.mailbox.email') }}
        <input v-model.trim="imapForm.mailbox_email" type="email" required />
      </label>
      <label>
        {{ i18nStore.t('frontend.mailbox.imap_host') }}
        <input v-model.trim="imapForm.imap_host" type="text" required />
      </label>
      <label>
        {{ i18nStore.t('frontend.mailbox.imap_port') }}
        <input v-model.number="imapForm.imap_port" type="number" min="1" max="65535" required />
      </label>
      <label>
        {{ i18nStore.t('frontend.mailbox.imap_password') }}
        <input v-model="imapForm.imap_password" type="password" required />
      </label>
      <label class="checkbox-label">
        <input v-model="imapForm.imap_ssl" type="checkbox" />
        {{ i18nStore.t('frontend.mailbox.imap_ssl') }}
      </label>
      <div class="form-actions">
        <button class="button button-secondary" type="button" @click="cancelImapSetup">
          {{ i18nStore.t('frontend.clients.clear') }}
        </button>
        <button class="button button-primary" type="submit" :disabled="isSavingImap">
          {{ isSavingImap ? i18nStore.t('frontend.mailbox.saving') : i18nStore.t('frontend.mailbox.save_imap') }}
        </button>
      </div>
    </form>

    <template v-if="mailbox">
      <div class="mailbox-info">
        <div class="mailbox-field">
          <span class="field-label">{{ i18nStore.t('frontend.mailbox.email') }}</span>
          <span class="field-value">{{ mailbox.mailbox_email }}</span>
        </div>
        <div class="mailbox-field">
          <span class="field-label">{{ i18nStore.t('frontend.mailbox.provider') }}</span>
          <span class="field-value provider-name">{{ mailbox.provider === 'google' ? 'Gmail' : mailbox.provider === 'microsoft' ? 'Outlook' : 'IMAP' }}</span>
        </div>
        <div class="mailbox-field">
          <span class="field-label">{{ i18nStore.t('frontend.mailbox.method') }}</span>
          <span class="field-value">{{ mailbox.auth_method === 'oauth' ? 'OAuth 2.0' : 'IMAP App Password' }}</span>
        </div>
        <div class="mailbox-field">
          <span class="field-label">{{ i18nStore.t('frontend.mailbox.status') }}</span>
          <span class="status-badge" :class="mailbox.status">{{
            mailbox.status === 'connected' ? i18nStore.t('frontend.mailbox.status_connected') :
            mailbox.status === 'disconnected' ? i18nStore.t('frontend.mailbox.status_disconnected') :
            mailbox.status === 'revoked' ? i18nStore.t('frontend.mailbox.status_revoked') :
            i18nStore.t('frontend.mailbox.status_error')
          }}</span>
        </div>
        <div v-if="mailbox.oauth_provider_email" class="mailbox-field">
          <span class="field-label">{{ i18nStore.t('frontend.mailbox.oauth_provider_email') }}</span>
          <span class="field-value">{{ mailbox.oauth_provider_email }}</span>
        </div>
        <div v-if="mailbox.imap_host" class="mailbox-field">
          <span class="field-label">{{ i18nStore.t('frontend.mailbox.imap_host') }}</span>
          <span class="field-value">{{ mailbox.imap_host }}:{{ mailbox.imap_port }}</span>
        </div>
        <div v-if="mailbox.last_connection_error" class="mailbox-field">
          <span class="field-label">{{ i18nStore.t('frontend.subscriptions.status') }}</span>
          <span class="field-value error-text">{{ mailbox.last_connection_error }}</span>
        </div>
      </div>

      <div class="mailbox-actions">
        <button
          v-if="mailbox.auth_method !== 'oauth'"
          class="button button-secondary"
          type="button"
          :disabled="isTestingMailbox"
          @click="testMailbox"
        >
          {{ isTestingMailbox ? i18nStore.t('frontend.mailbox.testing') : i18nStore.t('frontend.mailbox.test') }}
        </button>
        <button v-if="showConnectActions" class="button button-secondary" type="button" @click="openImapSetup('custom')">
          {{ i18nStore.t('frontend.mailbox.setup_imap') }}
        </button>
        <button v-if="isConnected" class="button button-secondary" type="button" :disabled="isDisconnectingMailbox" @click="disconnectMailbox">
          {{ isDisconnectingMailbox ? i18nStore.t('frontend.mailbox.disconnecting') : i18nStore.t('frontend.mailbox.disconnect') }}
        </button>
      </div>
    </template>
  </section>
</template>

<style scoped>
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
  background: var(--primary, #4f46e5);
  color: #ffffff;
}

.button-secondary {
  border: 1px solid var(--border, #e2e8f0);
  background: var(--card-bg, #ffffff);
  color: var(--text, #1e293b);
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
  color: var(--text-secondary, #64748b);
  font-weight: 700;
}

input {
  width: 100%;
  box-sizing: border-box;
  border: 1px solid var(--border, #e2e8f0);
  border-radius: 10px;
  padding: 11px 12px;
  color: var(--text, #1e293b);
  font: inherit;
}

input:focus {
  border-color: var(--primary, #4f46e5);
  outline: 3px solid rgb(79 70 229 / 15%);
}

.form-actions {
  grid-column: 1 / -1;
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}

.connection-sections {
  display: grid;
  gap: 14px;
  margin-top: 16px;
}

.connection-card {
  border: 1px solid var(--border, #e2e8f0);
  border-radius: 12px;
  padding: 14px;
}

.connection-card h3 {
  margin: 0;
}

.connection-card p {
  margin: 8px 0 0;
  color: var(--text-secondary, #64748b);
}

.helper-note {
  font-size: 0.85rem;
}

.recommended-card {
  border-color: var(--primary, #4f46e5);
  box-shadow: 0 1px 6px rgb(79 70 229 / 8%);
}

.provider-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin-top: 14px;
}

.provider-btn {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 6px;
  border: 1px solid var(--border, #e2e8f0);
  border-radius: 12px;
  padding: 14px 20px;
  background: var(--card-bg, #fff);
  color: var(--text, #1e293b);
  font: inherit;
  font-weight: 700;
  cursor: pointer;
  transition: border-color 0.15s, box-shadow 0.15s;
}

.provider-btn:hover {
  border-color: var(--primary, #4f46e5);
  box-shadow: 0 2px 8px rgb(79 70 229 / 12%);
}

.provider-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border-radius: 8px;
  background: var(--bg, #f8fafc);
  font-weight: 800;
  font-size: 0.85rem;
}

.provider-btn small {
  font-weight: 500;
  color: var(--text-secondary, #64748b);
}

.form-guidance {
  grid-column: 1 / -1;
  margin: 0;
  color: var(--text-secondary, #64748b);
  font-size: 0.9rem;
}

.mailbox-info {
  display: grid;
  gap: 12px;
  margin-top: 18px;
}

.mailbox-field {
  display: flex;
  align-items: center;
  gap: 10px;
}

.mailbox-field .field-label {
  color: var(--text-secondary, #64748b);
  font-weight: 700;
  font-size: 0.85rem;
  min-width: 130px;
}

.mailbox-field .field-value {
  font-weight: 600;
}

.mailbox-field .error-text {
  color: var(--danger, #ef4444);
}

.provider-name {
  text-transform: capitalize;
}

.status-badge {
  display: inline-flex;
  border-radius: 999px;
  padding: 5px 10px;
  font-size: 0.8rem;
  font-weight: 700;
}

.status-badge.connected {
  background: #dcfce7;
  color: #166534;
}

.status-badge.revoked {
  background: #fef3c7;
  color: #92400e;
}

.status-badge.error {
  background: rgb(239 68 68 / 10%);
  color: #b91c1c;
}

.mailbox-actions {
  display: flex;
  gap: 12px;
  margin-top: 20px;
}

.checkbox-label {
  display: flex;
  flex-direction: row;
  align-items: center;
  gap: 8px;
  color: var(--text-secondary, #64748b);
  font-weight: 700;
}
</style>
