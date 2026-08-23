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
    <div className="min-h-screen flex items-center justify-center bg-gray-50 px-4 py-10">
      <div className="w-full max-w-sm">
        <div className="flex items-center gap-2 justify-center mb-8">
          <div className="w-9 h-9 rounded-lg bg-brand-600 flex items-center justify-center">
            <Leaf size={20} className="text-white" />
          </div>
          <span className="text-xl font-semibold text-gray-900">FoodBridge</span>
        </div>

        <div className="card">
          <h1 className="text-lg font-semibold text-gray-900 mb-4">Create account</h1>
          {error && <div className="bg-red-50 text-red-700 text-sm rounded-lg px-3 py-2 mb-4">{error}</div>}

          <form onSubmit={submit} className="space-y-3">
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
              <input className="input-field" value={form.name} onChange={(e) => update('name', e.target.value)} required />
            </div>
            <div>
              <label className="label">Email</label>
              <input className="input-field" type="email" value={form.email} onChange={(e) => update('email', e.target.value)} required />
            </div>
            <div>
              <label className="label">Password</label>
              <input className="input-field" type="password" value={form.password} onChange={(e) => update('password', e.target.value)} required />
            </div>
            <div>
              <label className="label">Phone</label>
              <input className="input-field" value={form.phone} onChange={(e) => update('phone', e.target.value)} />
            </div>
            <div className="grid grid-cols-2 gap-3">
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
                  <input className="input-field" type="number" value={form.ngo_capacity_total}
                         onChange={(e) => update('ngo_capacity_total', parseInt(e.target.value))} />
                </div>
                <label className="flex items-center gap-2 text-sm text-gray-600">
                  <input type="checkbox" checked={form.ngo_has_cold_storage}
                         onChange={(e) => update('ngo_has_cold_storage', e.target.checked)} />
                  Has cold storage
                </label>
              </>
            )}
            {form.role === 'volunteer' && (
              <div>
                <label className="label">Vehicle capacity (plates)</label>
                <input className="input-field" type="number" value={form.volunteer_capacity_plates}
                       onChange={(e) => update('volunteer_capacity_plates', parseInt(e.target.value))} />
              </div>
            )}

            <button className="btn-primary w-full" disabled={loading}>
              {loading ? 'Creating…' : 'Create account'}
            </button>
          </form>

          <p className="text-xs text-gray-400 mt-4 text-center">
            Already registered? <Link to="/login" className="text-brand-700 font-medium">Sign in</Link>
          </p>
        </div>
      </div>
    </div>
  )
}
