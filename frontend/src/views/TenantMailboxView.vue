<script setup>
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import api from '@/services/api'
import DashboardLayout from '@/components/DashboardLayout.vue'
import PageHeader from '@/components/PageHeader.vue'
import InlineAlert from '@/components/InlineAlert.vue'
import MailboxConfigPanel from '@/components/MailboxConfigPanel.vue'

const route = useRoute()
const router = useRouter()
const mailbox = ref(null)
const errorMessage = ref('')
const successMessage = ref('')

async function loadMailbox() {
  errorMessage.value = ''
  try {
    const response = await api.get('/tenant/mailbox/')
    mailbox.value = response.data
  } catch (error) {
    if (error.response?.status === 404) {
      mailbox.value = null
      return
    }
    const detail = error.response?.data?.detail
    errorMessage.value = Array.isArray(detail) ? detail.map(item => item.msg || item.message || String(item)).join(', ') : detail || 'Could not load mailbox configuration.'
  }
}

function maybeShowOAuthSuccess() {
  if (route.query.mailbox_oauth === 'success') {
    successMessage.value = 'Mailbox connected successfully via OAuth.'
    const nextQuery = { ...route.query }
    delete nextQuery.mailbox_oauth
    router.replace({ path: route.path, query: nextQuery })
    setTimeout(() => { successMessage.value = '' }, 5000)
  }
}

onMounted(() => {
  loadMailbox()
  maybeShowOAuthSuccess()
})
</script>

<template>
  <DashboardLayout>
    <div class="space-y-6">
      <PageHeader title="Mailbox" description="Connect the mailbox used for code retrieval workflows." />
      <InlineAlert v-if="successMessage" variant="success" :message="successMessage" />
      <InlineAlert v-if="errorMessage" variant="error" :message="errorMessage" />
      <MailboxConfigPanel :mailbox="mailbox" @updated="loadMailbox" />
    </div>
  </DashboardLayout>
</template>
