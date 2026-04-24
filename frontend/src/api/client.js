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

export async function createShipment(token, payload) {
  return request('/shipments', {
    method: 'POST',
    body: payload,
    token,
  })
}

export async function updateShipmentStatus(token, shipmentId, payload) {
  return request(`/shipments/${shipmentId}/status`, {
    method: 'PATCH',
    body: payload,
    token,
  })
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

