export function humanizeCode(value) {
  if (!value) return '-'
  return String(value)
    .replace(/^shipment_/, '')
    .replace(/_/g, ' ')
    .trim()
}

export function humanizeStatus(value) {
  return humanizeCode(value)
}

export function formatDateTime(value) {
  if (!value) return '-'
  const dt = new Date(value)
  if (Number.isNaN(dt.getTime())) return String(value)
  return dt.toLocaleString()
}

export function relayDisplayName(relayId, relayNameById = {}) {
  if (!relayId) return '-'
  return relayNameById[relayId] || relayId
}
