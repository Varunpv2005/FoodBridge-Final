const BASE = import.meta.env.VITE_API_BASE_URL || '/api'

function authHeaders() {
  const token = localStorage.getItem('fb_token')
  return token ? { Authorization: `Bearer ${token}` } : {}
}

async function handle(res) {
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail || 'Request failed')
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

  // --- NGO ---
  ngoDonations: () => get('/ngo/donations'),
  ngoProfile: () => get('/ngo/profile'),
  confirmReceipt: (donationId) => post(`/ngo/donations/${donationId}/confirm-receipt`, {}),

  // --- Volunteer ---
  myDeliveries: () => get('/volunteer/deliveries'),
  startDelivery: (deliveryId) => post(`/volunteer/deliveries/${deliveryId}/start`, {}),
  updateLocation: (lat, lng) => post('/volunteer/location', { lat, lng }),
  arriveStop: (stopId) => post(`/volunteer/stops/${stopId}/arrive`, {}),

  // --- Admin ---
  overview: () => get('/admin/overview'),
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
  const base = (import.meta.env.VITE_WS_BASE_URL || `ws://${window.location.hostname}:8000`)
  return `${base}/ws/track/${channel}`
}
