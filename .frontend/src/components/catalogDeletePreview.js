export function isDeleteConfirmationValid(value) {
  const normalized = String(value || '').trim().toLowerCase()
  return normalized === 'confirmar' || normalized === 'confirm'
}

export function formatCount(t, count, oneKey, otherKey) {
  return t(count === 1 ? oneKey : otherKey, { count })
}

export function formatPreviewRow(row) {
  const expires = row.expires_at ? String(row.expires_at).slice(0, 10) : '—'
  return `${row.streaming_email} - ${row.client_name || '—'} - ${row.client_phone || '—'} - ${row.service_name}/${row.plan_name} - ${expires}`
}
