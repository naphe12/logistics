const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000'
const TOKEN_KEY = 'logix_token'
const REFRESH_TOKEN_KEY = 'logix_refresh_token'

function getStoredTokens() {
  return {
    accessToken: localStorage.getItem(TOKEN_KEY) || '',
    refreshToken: localStorage.getItem(REFRESH_TOKEN_KEY) || '',
  }
}

function saveStoredTokens(accessToken, refreshToken = '') {
  localStorage.setItem(TOKEN_KEY, accessToken)
  if (refreshToken) {
    localStorage.setItem(REFRESH_TOKEN_KEY, refreshToken)
  } else {
    localStorage.removeItem(REFRESH_TOKEN_KEY)
  }
  window.dispatchEvent(new Event('logix-auth-updated'))
}

function clearStoredTokens() {
  localStorage.removeItem(TOKEN_KEY)
  localStorage.removeItem(REFRESH_TOKEN_KEY)
  window.dispatchEvent(new Event('logix-auth-updated'))
}

function expireSession() {
  clearStoredTokens()
  window.dispatchEvent(new Event('logix-session-expired'))
}

function getWsBaseUrl() {
  const base = API_BASE_URL.replace(/\/+$/, '')
  if (base.startsWith('https://')) {
    return `wss://${base.slice('https://'.length)}`
  }
  if (base.startsWith('http://')) {
    return `ws://${base.slice('http://'.length)}`
  }
  return base
}

async function parseError(res) {
  const ct = res.headers.get('content-type') || ''
  if (ct.includes('application/json')) {
    const data = await res.json()
    if (typeof data?.detail === 'string') return data.detail
    if (data?.detail && typeof data.detail === 'object') {
      const message = typeof data.detail.message === 'string' ? data.detail.message : 'Request failed'
      const retry = data.detail.retry_after_seconds
      if (typeof retry === 'number') return `${message} Retry in ${retry}s.`
      return message
    }
    return JSON.stringify(data)
  }
  return res.text()
}

async function request(path, { method = 'GET', body, token } = {}) {
  const headers = { 'Content-Type': 'application/json' }
  const stored = getStoredTokens()
  const authToken = token || stored.accessToken
  if (authToken) headers.Authorization = `Bearer ${authToken}`

  let res = await fetch(`${API_BASE_URL}${path}`, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
  })

  if (res.status === 401 && path !== '/auth/refresh') {
    if (stored.refreshToken) {
      const refreshRes = await fetch(`${API_BASE_URL}/auth/refresh`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ refresh_token: stored.refreshToken }),
      })

      if (refreshRes.ok) {
        const refreshData = await refreshRes.json()
        saveStoredTokens(refreshData.access_token, refreshData.refresh_token || stored.refreshToken)

        const retryHeaders = { 'Content-Type': 'application/json' }
        retryHeaders.Authorization = `Bearer ${refreshData.access_token}`
        res = await fetch(`${API_BASE_URL}${path}`, {
          method,
          headers: retryHeaders,
          body: body ? JSON.stringify(body) : undefined,
        })
      } else {
        expireSession()
      }
    } else if (stored.accessToken) {
      expireSession()
    }
  }

  if (!res.ok) {
    const text = await parseError(res)
    throw new Error(text || `HTTP ${res.status}`)
  }

  const ct = res.headers.get('content-type') || ''
  if (ct.includes('application/json')) {
    return res.json()
  }
  return res.text()
}

export async function checkHealth() {
  return request('/health')
}

export async function login(phone) {
  return request('/auth/login', {
    method: 'POST',
    body: { phone_e164: phone },
  })
}

export async function requestOtp(phone) {
  return request('/auth/otp/request', {
    method: 'POST',
    body: { phone_e164: phone },
  })
}

export async function verifyOtp(phone, code) {
  return request('/auth/otp/verify', {
    method: 'POST',
    body: { phone_e164: phone, code },
  })
}

export async function refreshAccessToken(refreshToken) {
  return request('/auth/refresh', {
    method: 'POST',
    body: { refresh_token: refreshToken },
  })
}

export async function getCurrentUser(token) {
  return request('/auth/me', { token })
}

export async function createShipment(token, payload) {
  return request('/shipments', {
    method: 'POST',
    body: payload,
    token,
  })
}

export async function getShipmentInsuranceQuote(token, { declaredValue, insuranceOptIn = true }) {
  const qs = new URLSearchParams()
  qs.set('declared_value', String(declaredValue ?? 0))
  qs.set('insurance_opt_in', insuranceOptIn ? 'true' : 'false')
  return request(`/shipments/insurance/quote?${qs.toString()}`, { token })
}

export async function getShipmentInsurancePolicy(token) {
  return request('/shipments/insurance/policy', { token })
}

export async function updateShipmentStatus(token, shipmentId, payload) {
  return request(`/shipments/${shipmentId}/status`, {
    method: 'PATCH',
    body: payload,
    token,
  })
}

export async function getShipmentEta(token, shipmentId) {
  return request(`/shipments/${shipmentId}/eta`, { token })
}

export async function validatePickupCode(token, shipmentId, code) {
  return request(`/codes/shipments/${shipmentId}/pickup/validate`, {
    method: 'POST',
    body: { code },
    token,
  })
}

export async function confirmPickupCode(token, shipmentId, payload) {
  return request(`/codes/shipments/${shipmentId}/pickup/confirm`, {
    method: 'POST',
    body: payload,
    token,
  })
}

export async function simulateUssd({ sessionId, serviceCode, phoneNumber, text }) {
  const body = new URLSearchParams()
  body.set('sessionId', sessionId)
  body.set('serviceCode', serviceCode)
  body.set('phoneNumber', phoneNumber)
  body.set('text', text || '')

  const res = await fetch(`${API_BASE_URL}/ussd`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: body.toString(),
  })

  if (!res.ok) {
    const message = await parseError(res)
    throw new Error(message || `HTTP ${res.status}`)
  }
  return res.text()
}

export async function listUsers(token, role) {
  const query = role ? `?role=${encodeURIComponent(role)}` : ''
  return request(`/auth/users${query}`, { token })
}

export async function listRelays(token) {
  return request('/relays', { token })
}

export async function createRelay(token, payload) {
  return request('/relays', {
    method: 'POST',
    body: payload,
    token,
  })
}

export async function updateRelay(token, relayId, payload) {
  return request(`/relays/${relayId}`, {
    method: 'PATCH',
    body: payload,
    token,
  })
}

export async function deleteRelay(token, relayId) {
  return request(`/relays/${relayId}`, {
    method: 'DELETE',
    token,
  })
}

export async function listRelayAgents(token, relayId) {
  return request(`/relays/${relayId}/agents`, { token })
}

export async function listRelayInventory(token, relayId, presentOnly = false) {
  const suffix = presentOnly ? '?present_only=true' : ''
  return request(`/relays/${relayId}/inventory${suffix}`, { token })
}

export async function getRelayCapacity(token, relayId) {
  return request(`/relays/${relayId}/capacity`, { token })
}

export async function upsertRelayInventory(token, relayId, payload) {
  return request(`/relays/${relayId}/inventory`, {
    method: 'PUT',
    body: payload,
    token,
  })
}

export async function assignAgentToRelay(token, relayId, userId) {
  return request(`/relays/${relayId}/agents/${userId}`, {
    method: 'PUT',
    token,
  })
}

export async function unassignAgentFromRelay(token, relayId, userId) {
  return request(`/relays/${relayId}/agents/${userId}`, {
    method: 'DELETE',
    token,
  })
}

export async function listTrips(token) {
  return request('/transport/trips', { token })
}

export async function createTrip(token, payload) {
  return request('/transport/trips', {
    method: 'POST',
    body: payload,
    token,
  })
}

export async function updateTrip(token, tripId, payload) {
  return request(`/transport/trips/${tripId}`, {
    method: 'PATCH',
    body: payload,
    token,
  })
}

export async function getTripManifest(token, tripId) {
  return request(`/transport/trips/${tripId}/manifest`, { token })
}

export async function addShipmentToManifest(token, tripId, shipmentId) {
  return request(`/transport/trips/${tripId}/manifest/shipments`, {
    method: 'POST',
    body: { shipment_id: shipmentId },
    token,
  })
}

export async function removeShipmentFromManifest(token, tripId, shipmentId) {
  return request(`/transport/trips/${tripId}/manifest/shipments/${shipmentId}`, {
    method: 'DELETE',
    token,
  })
}

export async function scanTripDeparture(token, tripId, payload = {}) {
  return request(`/transport/trips/${tripId}/scan/departure`, {
    method: 'POST',
    body: payload,
    token,
  })
}

export async function scanTripArrival(token, tripId, payload = {}) {
  return request(`/transport/trips/${tripId}/scan/arrival`, {
    method: 'POST',
    body: payload,
    token,
  })
}

export async function completeTrip(token, tripId) {
  return request(`/transport/trips/${tripId}/complete`, {
    method: 'POST',
    token,
  })
}

export async function getTransportGroupingSuggestions(token, { maxGroupSize = 10, limit = 300 } = {}) {
  const qs = new URLSearchParams()
  qs.set('max_group_size', String(maxGroupSize))
  qs.set('limit', String(limit))
  return request(`/transport/optimizer/grouping?${qs.toString()}`, { token })
}

export async function getTransportPrioritySuggestions(token, { maxResults = 50, limit = 500 } = {}) {
  const qs = new URLSearchParams()
  qs.set('max_results', String(maxResults))
  qs.set('limit', String(limit))
  return request(`/transport/optimizer/priority?${qs.toString()}`, { token })
}

export async function autoAssignPriorityToTrip(
  token,
  tripId,
  { targetManifestSize = 20, maxAdd = 10, candidateLimit = 500, vehicleCapacity = null } = {},
) {
  const body = {
    target_manifest_size: targetManifestSize,
    max_add: maxAdd,
    candidate_limit: candidateLimit,
  }
  if (vehicleCapacity !== null && vehicleCapacity !== undefined && vehicleCapacity > 0) {
    body.vehicle_capacity = vehicleCapacity
  }
  return request(`/transport/trips/${tripId}/manifest/auto-assign-priority`, {
    method: 'POST',
    body,
    token,
  })
}

export async function listPaymentStatuses(token) {
  return request('/payments/statuses', { token })
}

export async function listPayments(token, filters = {}) {
  const qs = new URLSearchParams()
  if (filters.shipment_id) qs.set('shipment_id', filters.shipment_id)
  if (filters.status) qs.set('status', filters.status)
  if (filters.payer_phone) qs.set('payer_phone', filters.payer_phone)
  const suffix = qs.toString() ? `?${qs.toString()}` : ''
  return request(`/payments${suffix}`, { token })
}

export async function createPayment(token, payload) {
  return request('/payments', {
    method: 'POST',
    body: payload,
    token,
  })
}

export async function initiatePayment(token, paymentId, externalRef = '') {
  return request(`/payments/${paymentId}/initiate`, {
    method: 'POST',
    body: { external_ref: externalRef || null },
    token,
  })
}

export async function confirmPayment(token, paymentId, externalRef = '') {
  return request(`/payments/${paymentId}/confirm`, {
    method: 'POST',
    body: { external_ref: externalRef || null },
    token,
  })
}

export async function failPayment(token, paymentId, reason) {
  return request(`/payments/${paymentId}/fail`, {
    method: 'POST',
    body: { reason },
    token,
  })
}

export async function cancelPayment(token, paymentId) {
  return request(`/payments/${paymentId}/cancel`, {
    method: 'POST',
    token,
  })
}

export async function refundPayment(token, paymentId, reason) {
  return request(`/payments/${paymentId}/refund`, {
    method: 'POST',
    body: { reason },
    token,
  })
}

export async function listCommissions(token, filters = {}) {
  const qs = new URLSearchParams()
  if (filters.shipment_id) qs.set('shipment_id', filters.shipment_id)
  if (filters.payment_id) qs.set('payment_id', filters.payment_id)
  const suffix = qs.toString() ? `?${qs.toString()}` : ''
  return request(`/payments/commissions${suffix}`, { token })
}

export async function listIncidentStatuses(token) {
  return request('/incidents/statuses', { token })
}

export async function listIncidents(token, filters = {}) {
  const qs = new URLSearchParams()
  if (filters.shipment_id) qs.set('shipment_id', filters.shipment_id)
  if (filters.status) qs.set('status', filters.status)
  if (filters.incident_type) qs.set('incident_type', filters.incident_type)
  const suffix = qs.toString() ? `?${qs.toString()}` : ''
  return request(`/incidents${suffix}`, { token })
}

export async function createIncident(token, payload) {
  return request('/incidents', {
    method: 'POST',
    body: payload,
    token,
  })
}

export async function updateIncidentStatus(token, incidentId, status) {
  return request(`/incidents/${incidentId}/status`, {
    method: 'PATCH',
    body: { status },
    token,
  })
}

export async function listIncidentUpdates(token, incidentId) {
  return request(`/incidents/${incidentId}/updates`, { token })
}

export async function addIncidentUpdate(token, incidentId, message) {
  return request(`/incidents/${incidentId}/updates`, {
    method: 'POST',
    body: { message },
    token,
  })
}

export async function listClaims(token, filters = {}) {
  const qs = new URLSearchParams()
  if (filters.incident_id) qs.set('incident_id', filters.incident_id)
  if (filters.shipment_id) qs.set('shipment_id', filters.shipment_id)
  if (filters.status) qs.set('status', filters.status)
  const suffix = qs.toString() ? `?${qs.toString()}` : ''
  return request(`/incidents/claims${suffix}`, { token })
}

export async function createClaim(token, payload) {
  return request('/incidents/claims', {
    method: 'POST',
    body: payload,
    token,
  })
}

export async function updateClaimStatus(token, claimId, payload) {
  return request(`/incidents/claims/${claimId}/status`, {
    method: 'PATCH',
    body: payload,
    token,
  })
}

export async function getBackofficeOverview(token) {
  return request('/backoffice/overview', { token })
}

export async function listBackofficeSmsLogs(token, limit = 100) {
  return request(`/backoffice/logs/sms?limit=${limit}`, { token })
}

export async function listBackofficeUssdLogs(token, limit = 100) {
  return request(`/backoffice/logs/ussd?limit=${limit}`, { token })
}

export async function listBackofficeAuditLogs(token, limit = 100) {
  return request(`/backoffice/logs/audit?limit=${limit}`, { token })
}

export async function listBackofficeErrors(token, limit = 100) {
  return request(`/backoffice/errors/recent?limit=${limit}`, { token })
}

export async function dispatchBackofficeSms(token, limit = 100) {
  return request(`/backoffice/sms/dispatch?limit=${limit}`, {
    method: 'POST',
    token,
  })
}

export async function getBackofficeSmsWorkerStatus(token) {
  return request('/backoffice/sms/worker/status', { token })
}

export async function listBackofficeAlerts(token, params = {}) {
  const qs = new URLSearchParams()
  if (params.delayed_hours) qs.set('delayed_hours', String(params.delayed_hours))
  if (params.relay_utilization_warn !== undefined) {
    qs.set('relay_utilization_warn', String(params.relay_utilization_warn))
  }
  if (params.limit) qs.set('limit', String(params.limit))
  const suffix = qs.toString() ? `?${qs.toString()}` : ''
  return request(`/backoffice/alerts${suffix}`, { token })
}

export async function runBackofficeAutoDetectIncidents(token, delayedHours = 48, limit = 200) {
  const qs = new URLSearchParams()
  qs.set('delayed_hours', String(delayedHours))
  qs.set('limit', String(limit))
  return request(`/backoffice/incidents/auto-detect?${qs.toString()}`, {
    method: 'POST',
    token,
  })
}

export async function notifyBackofficeCriticalAlertsSms(
  token,
  {
    delayedHours = 48,
    relayUtilizationWarn = 0.9,
    throttleMinutes = 30,
    maxRecipients = 20,
    maxPerHour = 4,
  } = {},
) {
  const qs = new URLSearchParams()
  qs.set('delayed_hours', String(delayedHours))
  qs.set('relay_utilization_warn', String(relayUtilizationWarn))
  qs.set('throttle_minutes', String(throttleMinutes))
  qs.set('max_recipients', String(maxRecipients))
  qs.set('max_per_hour', String(maxPerHour))
  return request(`/backoffice/alerts/notify-critical?${qs.toString()}`, {
    method: 'POST',
    token,
  })
}

export function openShipmentTrackingSocket(token, shipmentId, handlers = {}) {
  if (!token) throw new Error('Missing token')
  if (!shipmentId) throw new Error('Missing shipment id')
  const wsUrl = `${getWsBaseUrl()}/ws/shipments/${encodeURIComponent(shipmentId)}?token=${encodeURIComponent(token)}`
  const ws = new WebSocket(wsUrl)

  if (handlers.onOpen) ws.addEventListener('open', handlers.onOpen)
  if (handlers.onClose) ws.addEventListener('close', handlers.onClose)
  if (handlers.onError) ws.addEventListener('error', handlers.onError)
  if (handlers.onMessage) {
    ws.addEventListener('message', (event) => {
      try {
        handlers.onMessage(JSON.parse(event.data))
      } catch {
        handlers.onMessage({ kind: 'raw', value: String(event.data || '') })
      }
    })
  }

  return ws
}

