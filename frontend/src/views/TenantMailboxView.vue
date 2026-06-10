<script setup>
import { onMounted, ref } from 'vue'
import api from '@/services/api'
import DashboardLayout from '@/components/DashboardLayout.vue'
import PageHeader from '@/components/PageHeader.vue'
import InlineAlert from '@/components/InlineAlert.vue'
import MailboxConfigPanel from '@/components/MailboxConfigPanel.vue'

const mailbox = ref(null)
const errorMessage = ref('')

async function loadMailbox() {
  errorMessage.value = ''
  try {
    const response = await api.get('/tenant/mailbox/')
    mailbox.value = response.data
  } catch (error) {
    const detail = error.response?.data?.detail
    errorMessage.value = Array.isArray(detail) ? detail.map(item => item.msg || item.message || String(item)).join(', ') : detail || 'Could not load mailbox configuration.'
  }
}

onMounted(loadMailbox)
</script>

<template>
  <DashboardLayout>
    <div class="space-y-6">
      <PageHeader title="Mailbox" description="Connect the mailbox used for code retrieval workflows." />
      <InlineAlert v-if="errorMessage" variant="error" :message="errorMessage" />
      <MailboxConfigPanel :mailbox="mailbox" @updated="loadMailbox" />
    </div>
  </DashboardLayout>
</template>
