const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000'

async function parseError(res) {
  const ct = res.headers.get('content-type') || ''
  if (ct.includes('application/json')) {
    const data = await res.json()
    if (typeof data?.detail === 'string') return data.detail
    return JSON.stringify(data)
  }
  return res.text()
}

async function request(path, { method = 'GET', body, token } = {}) {
  const headers = { 'Content-Type': 'application/json' }
  if (token) headers.Authorization = `Bearer ${token}`

  const res = await fetch(`${API_BASE_URL}${path}`, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
  })

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

export async function login(phone, password) {
  const form = new URLSearchParams()
  form.set('username', phone)
  form.set('password', password)

  const res = await fetch(`${API_BASE_URL}/auth/token`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: form.toString(),
  })

  if (!res.ok) {
    const text = await parseError(res)
    throw new Error(text || `HTTP ${res.status}`)
  }

  return res.json()
}

export async function registerUser(payload) {
  return request('/auth/register', {
    method: 'POST',
    body: payload,
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

