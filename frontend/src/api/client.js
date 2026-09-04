const BASE = import.meta.env.VITE_API_BASE_URL || '/api'

function authHeaders() {
  const token = localStorage.getItem('fb_token')
  return token ? { Authorization: `Bearer ${token}` } : {}
}

function friendlyError(message) {
  const text = String(message || '').toLowerCase()
  if (text.includes('failed to fetch') || text.includes('networkerror') || text.includes('load failed')) {
    return "We couldn't reach FoodBridge. Please check your connection and try again."
  }
  if (text.includes('not found')) {
    return 'This item could not be found right now.'
  }
  return message || 'Request failed'
}

async function handle(res) {
  if (!res.ok) {
    if (res.status === 401) {
      localStorage.removeItem('fb_token')
      window.dispatchEvent(new Event('foodbridge:unauthorized'))
    }
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    const detail = err.detail
    const message = Array.isArray(detail)
      ? detail.map((item) => item.msg || item.message || String(item)).join(', ')
      : detail && typeof detail === 'object'
        ? detail.message || JSON.stringify(detail)
        : detail || 'Request failed'
    throw new Error(friendlyError(message))
  }
  return res.json()
}

function get(path) {
  return fetch(`${BASE}${path}`, { headers: { ...authHeaders() } }).then(handle)
}
function post(path, body) {
  return fetch(`${BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify(body),
  }).then(handle)
}

export const api = {
  // --- Auth ---
  register: (payload) => post('/auth/register', payload),
  login: (payload) => post('/auth/login', payload),
  me: () => get('/auth/me'),

  // --- Donor ---
  createDonation: (formData) =>
    fetch(`${BASE}/donor/donations`, { method: 'POST', headers: { ...authHeaders() }, body: formData }).then(handle),
  myDonations: () => get('/donor/donations'),
  getDonation: (id) => get(`/donor/donations/${id}`),
  assistantChat: async (payload) => {
    const response = await post('/assistant/chat', payload)
    if (!response || typeof response.reply !== 'string'
      || typeof response.language !== 'string' || typeof response.intent !== 'string') {
      throw new Error('The assistant returned an invalid response.')
    }
    return response
  },
  assistantKannadaAudio: (payload) => fetch(`${BASE}/tts`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify(payload),
  }).then(async (response) => {
    const contentType = response.headers.get('content-type') || ''
    console.info('[FoodBridge TTS] response', { status: response.status, contentType })
    if (!response.ok) {
      const errorBody = await response.text()
      console.error('[FoodBridge TTS] backend error', { status: response.status, body: errorBody.slice(0, 300) })
      throw new Error('Kannada audio is temporarily unavailable.')
    }
    if (!contentType.startsWith('audio/')) {
      console.error('[FoodBridge TTS] unexpected response type', { contentType })
      throw new Error('Kannada audio is temporarily unavailable.')
    }
    return response.blob()
  }),
  estimateRisk: (payload) => post('/ml/risk/estimate', payload),
  demandForecast: (horizon = 7) => get(`/ml/demand/forecast?horizon=${horizon}`),

  // --- NGO ---
  ngoDonations: () => get('/ngo/donations'),
  ngoProfile: () => get('/ngo/profile'),
  confirmReceipt: (donationId) => post(`/ngo/donations/${donationId}/confirm-receipt`, {}),
  rejectDonation: (donationId) => post(`/ngo/donations/${donationId}/reject`, {}),

  // --- Volunteer ---
  myDeliveries: () => get('/volunteer/deliveries'),
  startDelivery: (deliveryId) => post(`/volunteer/deliveries/${deliveryId}/start`, {}),
  updateLocation: (deliveryId, lat, lng, accuracy, timestamp) => post('/volunteer/location', {
    delivery_id: deliveryId, lat, lng, accuracy, timestamp,
  }),
  arriveStop: (stopId) => post(`/volunteer/stops/${stopId}/arrive`, {}),

  // --- Admin ---
  overview: () => get('/admin/overview'),
  evaluationResults: () => get('/admin/results'),
  allDonations: () => get('/admin/donations'),
  allDeliveries: () => get('/admin/deliveries'),
  allUsers: () => get('/admin/users'),
  anomalyQueue: () => get('/admin/anomalies'),
  approveAnomaly: (id) => post(`/admin/anomalies/${id}/approve`, {}),
  rejectAnomaly: (id) => post(`/admin/anomalies/${id}/reject`, {}),

  // --- Feedback ---
  submitFeedback: (payload) => post('/feedback', payload),
  feedbackFor: (targetId) => get(`/feedback/for/${targetId}`),

  // --- Standalone ML playground (kept from v1) ---
  mlMetrics: () => get('/metrics'),
  mlImageQuality: (file) => {
    const form = new FormData()
    form.append('file', file)
    return fetch(`${BASE}/ml/image-quality/predict`, { method: 'POST', body: form }).then(handle)
  },
  mlSentiment: (comment_text) => post('/ml/sentiment/predict', { comment_text }),
  mlMatching: (payload) => post('/ml/matching/predict', payload),
  mlAnomaly: (payload) => post('/ml/anomaly/predict', payload),
}

export function wsUrl(channel) {
  const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws'
  const isLocal = window.location.hostname === '127.0.0.1' || window.location.hostname === 'localhost'
  const base = isLocal
    ? `${protocol}://127.0.0.1:8000`
    : (import.meta.env.VITE_WS_BASE_URL || `${protocol}://${window.location.host}`)
  const token = localStorage.getItem('fb_token')
  const query = token ? `?token=${encodeURIComponent(token)}` : ''
  return `${base}/ws/track/${encodeURIComponent(channel)}${query}`
}
