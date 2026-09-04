import { useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { Leaf } from 'lucide-react'

export default function Register() {
  const [form, setForm] = useState({
    name: '', email: '', password: '', role: 'donor', phone: '',
    lat: 12.3052, lng: 76.6552,
    ngo_capacity_total: 100, ngo_has_cold_storage: false, ngo_tier: 1,
    volunteer_capacity_plates: 60,
  })
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const { register } = useAuth()
  const navigate = useNavigate()

  const update = (key, value) => setForm((f) => ({ ...f, [key]: value }))

  const submit = async (e) => {
    e.preventDefault()
    setLoading(true)
    setError('')
    try {
      const user = await register(form)
      navigate(`/${user.role}`)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-brand-50 via-white to-gray-50 px-4 py-10">
      <div className="mx-auto max-w-4xl overflow-hidden rounded-[32px] border border-gray-200 bg-white shadow-sm">
        <div className="grid lg:grid-cols-[1.1fr_1.4fr]">
          <div className="bg-brand-600 p-8 text-white lg:p-10">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-white/15">
                <Leaf size={22} />
              </div>
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.18em] text-brand-100">FoodBridge</p>
                <p className="text-xl font-semibold">Join the network</p>
              </div>
            </div>

            <div className="mt-8 space-y-5">
              <h1 className="text-4xl font-semibold leading-tight">Create your account and start helping faster.</h1>
              <p className="text-base text-brand-100">Whether you are donating surplus food, receiving it, or coordinating deliveries, the flow is designed to get you operational quickly.</p>
            </div>

            <div className="mt-10 space-y-3 text-sm text-brand-50">
              <div className="rounded-2xl border border-white/15 bg-white/5 p-4">Donor: upload food and get matched fast</div>
              <div className="rounded-2xl border border-white/15 bg-white/5 p-4">NGO: review priorities and accept donations</div>
              <div className="rounded-2xl border border-white/15 bg-white/5 p-4">Volunteer: manage routes and live tracking</div>
            </div>
          </div>

          <div className="p-6 sm:p-8 lg:p-10">
            <div className="mb-6">
              <p className="text-xs font-semibold uppercase tracking-[0.14em] text-brand-700">Create account</p>
              <h2 className="mt-2 text-3xl font-semibold text-gray-900">Get started</h2>
            </div>

            {error && <div className="mb-4 rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{error}</div>}

            <form onSubmit={submit} className="space-y-4">
              <div>
                <label className="label">I am a...</label>
                <select className="input-field" value={form.role} onChange={(e) => update('role', e.target.value)}>
                  <option value="donor">Donor</option>
                  <option value="ngo">NGO</option>
                  <option value="volunteer">Volunteer</option>
                </select>
              </div>

              <div>
                <label className="label">Name / Organization</label>
                <input className="input-field" value={form.name} onChange={(e) => update('name', e.target.value)} placeholder="Full name or organization name" required />
              </div>

              <div>
                <label className="label">Email</label>
                <input className="input-field" type="email" value={form.email} onChange={(e) => update('email', e.target.value)} placeholder="you@example.com" required />
              </div>

              <div>
                <label className="label">Password</label>
                <input className="input-field" type="password" value={form.password} onChange={(e) => update('password', e.target.value)} placeholder="Create a password" required />
              </div>

              <div>
                <label className="label">Phone</label>
                <input className="input-field" value={form.phone} onChange={(e) => update('phone', e.target.value)} placeholder="Optional contact phone" />
              </div>

              <div className="grid gap-3 sm:grid-cols-2">
                <div>
                  <label className="label">Latitude</label>
                  <input className="input-field" type="number" step="0.0001" value={form.lat} onChange={(e) => update('lat', parseFloat(e.target.value))} />
                </div>
                <div>
                  <label className="label">Longitude</label>
                  <input className="input-field" type="number" step="0.0001" value={form.lng} onChange={(e) => update('lng', parseFloat(e.target.value))} />
                </div>
              </div>

              {form.role === 'ngo' && (
                <>
                  <div>
                    <label className="label">Total capacity (plates)</label>
                    <input className="input-field" type="number" value={form.ngo_capacity_total} onChange={(e) => update('ngo_capacity_total', parseInt(e.target.value))} />
                  </div>
                  <label className="flex items-center gap-2 text-sm text-gray-600">
                    <input type="checkbox" checked={form.ngo_has_cold_storage} onChange={(e) => update('ngo_has_cold_storage', e.target.checked)} />
                    Has cold storage
                  </label>
                </>
              )}
              {form.role === 'volunteer' && (
                <div>
                  <label className="label">Vehicle capacity (plates)</label>
                  <input className="input-field" type="number" value={form.volunteer_capacity_plates} onChange={(e) => update('volunteer_capacity_plates', parseInt(e.target.value))} />
                </div>
              )}

              <button className="btn-primary w-full" disabled={loading}>
                {loading ? 'Creating account…' : 'Create account'}
              </button>
            </form>

            <p className="mt-6 text-center text-sm text-gray-500">
              Already have an account? <Link to="/login" className="font-semibold text-brand-700">Sign in</Link>
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}
