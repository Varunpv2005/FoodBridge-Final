import { useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { Leaf } from 'lucide-react'

const DEMO_ACCOUNTS = [
  { label: 'Donor', email: 'donor1@foodbridge.demo' },
  { label: 'NGO', email: 'ngo1@foodbridge.demo' },
  { label: 'Volunteer', email: 'volunteer2@foodbridge.demo' },
  { label: 'Admin', email: 'admin@foodbridge.demo' },
]

export default function Login() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('demo1234')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const { login } = useAuth()
  const navigate = useNavigate()

  const submit = async (e) => {
    e.preventDefault()
    setLoading(true)
    setError('')
    try {
      const user = await login(email, password)
      navigate(`/${user.role}`)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  const handleDemoLogin = async (demoEmail) => {
    setLoading(true)
    setError('')
    try {
      const user = await login(demoEmail, 'demo1234')
      navigate(`/${user.role}`)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-brand-50 via-white to-gray-50 px-4 py-10">
      <div className="mx-auto max-w-5xl overflow-hidden rounded-[32px] border border-gray-200 bg-white shadow-sm">
        <div className="grid min-h-[720px] lg:grid-cols-2">
          <div className="flex flex-col justify-between bg-brand-600 p-8 text-white lg:p-10">
            <div>
              <div className="mb-8 flex items-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-white/15">
                  <Leaf size={22} />
                </div>
                <div>
                  <p className="text-xs font-semibold uppercase tracking-[0.18em] text-brand-100">FoodBridge</p>
                  <p className="text-xl font-semibold">Redistribution platform</p>
                </div>
              </div>

              <div className="max-w-md space-y-5">
                <h1 className="text-4xl font-semibold leading-tight">Turn surplus food into timely action.</h1>
                <p className="text-base text-brand-100">Connect donors, NGOs, volunteers, and operations teams in one real-time food recovery workflow.</p>
              </div>
            </div>

            <div className="mt-10 grid gap-3 text-sm text-brand-50">
              <div className="rounded-2xl border border-white/15 bg-white/5 p-4">Live matching and delivery coordination</div>
              <div className="rounded-2xl border border-white/15 bg-white/5 p-4">AI-assisted spoilage and demand insights</div>
              <div className="rounded-2xl border border-white/15 bg-white/5 p-4">Operations visibility for every role</div>
            </div>
          </div>

          <div className="flex items-center justify-center p-6 sm:p-8 lg:p-10">
            <div className="w-full max-w-md">
              <div className="mb-8">
                <p className="text-xs font-semibold uppercase tracking-[0.14em] text-brand-700">Welcome back</p>
                <h2 className="mt-2 text-3xl font-semibold text-gray-900">Sign in</h2>
              </div>

              {error && <div className="mb-4 rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{error}</div>}

              <form onSubmit={submit} className="space-y-4">
                <div>
                  <label className="label">Email</label>
                  <input className="input-field" type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="name@foodbridge.com" required />
                </div>
                <div>
                  <label className="label">Password</label>
                  <input className="input-field" type="password" value={password} onChange={(e) => setPassword(e.target.value)} placeholder="Enter password" required />
                </div>
                <button className="btn-primary w-full" disabled={loading}>
                  {loading ? 'Signing in…' : 'Sign in'}
                </button>
              </form>

              <div className="mt-6 rounded-2xl border border-gray-200 bg-gray-50 p-4">
                <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-gray-500">Quick demo access</p>
                <div className="mt-3 grid gap-2 sm:grid-cols-2">
                  {DEMO_ACCOUNTS.map((d) => (
                    <button
                      key={d.email}
                      type="button"
                      onClick={() => handleDemoLogin(d.email)}
                      disabled={loading}
                      className="rounded-xl border border-gray-200 bg-white px-3 py-2 text-left text-xs text-gray-700 transition hover:border-brand-200 hover:bg-brand-50 disabled:cursor-not-allowed disabled:opacity-60"
                    >
                      <span className="block font-semibold text-gray-800">{d.label}</span>
                      <span className="mt-0.5 block text-gray-500">{d.email}</span>
                    </button>
                  ))}
                </div>
              </div>

              <p className="mt-6 text-center text-sm text-gray-500">
                No account yet? <Link to="/register" className="font-semibold text-brand-700">Create one</Link>
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
