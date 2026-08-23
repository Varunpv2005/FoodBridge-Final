import { useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { Leaf } from 'lucide-react'

const DEMO_ACCOUNTS = [
  { label: 'Donor', email: 'donor1@foodbridge.demo' },
  { label: 'NGO', email: 'ngo1@foodbridge.demo' },
  { label: 'Volunteer', email: 'volunteer1@foodbridge.demo' },
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

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 px-4">
      <div className="w-full max-w-sm">
        <div className="flex items-center gap-2 justify-center mb-8">
          <div className="w-9 h-9 rounded-lg bg-brand-600 flex items-center justify-center">
            <Leaf size={20} className="text-white" />
          </div>
          <span className="text-xl font-semibold text-gray-900">FoodBridge</span>
        </div>

        <div className="card">
          <h1 className="text-lg font-semibold text-gray-900 mb-1">Sign in</h1>
          <p className="text-sm text-gray-500 mb-5">Real-time food donation redistribution platform.</p>

          {error && <div className="bg-red-50 text-red-700 text-sm rounded-lg px-3 py-2 mb-4">{error}</div>}

          <form onSubmit={submit} className="space-y-3">
            <div>
              <label className="label">Email</label>
              <input className="input-field" type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
            </div>
            <div>
              <label className="label">Password</label>
              <input className="input-field" type="password" value={password} onChange={(e) => setPassword(e.target.value)} required />
            </div>
            <button className="btn-primary w-full" disabled={loading}>
              {loading ? 'Signing in…' : 'Sign in'}
            </button>
          </form>

          <p className="text-xs text-gray-400 mt-4 text-center">
            No account? <Link to="/register" className="text-brand-700 font-medium">Register</Link>
          </p>
        </div>

        <div className="card mt-4">
          <p className="text-xs font-medium text-gray-500 mb-2">Quick demo login (password: demo1234)</p>
          <div className="grid grid-cols-2 gap-2">
            {DEMO_ACCOUNTS.map((d) => (
              <button
                key={d.email}
                onClick={() => { setEmail(d.email); setPassword('demo1234') }}
                className="text-xs px-3 py-2 rounded-lg bg-gray-50 hover:bg-gray-100 text-gray-600 text-left"
              >
                {d.label}<br /><span className="text-gray-400">{d.email}</span>
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
