import { NavLink, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import {
  LayoutDashboard, Camera, Package, Users, Truck, ShieldAlert,
  Leaf, LogOut, MapPin, MessageSquareText, FlaskConical,
} from 'lucide-react'
import AssistantPanel from './AssistantPanel'

const NAV_BY_ROLE = {
  donor: [
    { to: '/donor', label: 'My Donations', icon: Package, end: true },
    { to: '/donor/new', label: 'New Donation', icon: Camera },
  ],
  ngo: [
    { to: '/ngo', label: 'Incoming Donations', icon: Package, end: true },
  ],
  volunteer: [
    { to: '/volunteer', label: '🚚 My Deliveries', icon: Truck, end: true },
  ],
  admin: [
    { to: '/admin', label: 'Overview', icon: LayoutDashboard, end: true },
    { to: '/admin/map', label: 'Live Map', icon: MapPin },
    { to: '/admin/anomalies', label: 'Anomaly Queue', icon: ShieldAlert },
    { to: '/admin/users', label: 'Users', icon: Users },
    { to: '/admin/ml', label: 'ML Playground', icon: MessageSquareText },
    { to: '/admin/results', label: 'Results & Evaluation', icon: FlaskConical },
  ],
}

export default function Layout({ children }) {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const links = NAV_BY_ROLE[user?.role] || []

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  return (
    <div className="min-h-screen flex">
      <aside className="hidden w-60 shrink-0 flex-col border-r border-gray-200 bg-white md:flex">
        <div className="flex items-center gap-2 px-6 py-5 border-b border-gray-100">
          <div className="w-8 h-8 rounded-lg bg-brand-600 flex items-center justify-center">
            <Leaf size={18} className="text-white" />
          </div>
          <div>
            <p className="font-semibold text-gray-900 leading-tight">FoodBridge</p>
            <p className="text-xs leading-tight text-gray-500 capitalize">{user?.role} Console</p>
          </div>
        </div>
        <nav className="flex-1 space-y-1 px-3 py-4">
          {links.map(({ to, label, icon: Icon, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              title={label}
              className={({ isActive }) =>
                `flex items-center gap-3 rounded-xl border px-3 py-2.5 text-sm font-medium transition-colors ${
                  isActive ? 'border-brand-100 bg-brand-50 text-brand-800' : 'border-transparent text-gray-600 hover:bg-gray-50'
                }`
              }
            >
              <Icon size={17} />
              {label}
            </NavLink>
          ))}
        </nav>
        <div className="px-4 py-4 border-t border-gray-100">
          <div className="flex items-center justify-between gap-3 px-2">
            <div className="min-w-0">
              <p className="text-sm font-semibold text-gray-800 truncate">{user?.name || 'Volunteer'}</p>
              <p className="text-xs text-gray-500 truncate">{user?.role ? user.role.charAt(0).toUpperCase() + user.role.slice(1) : 'Volunteer'}</p>
            </div>
            <button onClick={handleLogout} className="text-gray-400 hover:text-red-500 shrink-0 ml-2" aria-label="Log out">
              <LogOut size={16} />
            </button>
          </div>
        </div>
      </aside>
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex items-center justify-between border-b border-gray-200 bg-white px-4 py-3 md:hidden">
          <div className="flex min-w-0 items-center gap-2">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-brand-600"><Leaf size={17} className="text-white" /></div>
            <div className="min-w-0">
              <p className="truncate text-sm font-semibold text-gray-900">FoodBridge</p>
              <p className="text-xs capitalize text-gray-500">{user?.role} console</p>
            </div>
          </div>
          <button onClick={handleLogout} className="rounded-lg p-2 text-gray-500 hover:bg-gray-50 hover:text-red-600" aria-label="Log out" title="Log out">
            <LogOut size={17} />
          </button>
        </header>
        <nav className="flex gap-1 overflow-x-auto border-b border-gray-200 bg-white px-3 py-2 md:hidden" aria-label="Mobile navigation">
          {links.map(({ to, label, icon: Icon, end }) => (
            <NavLink key={to} to={to} end={end} title={label} className={({ isActive }) => `inline-flex min-h-10 shrink-0 items-center gap-2 rounded-lg border px-3 py-2 text-sm font-medium ${isActive ? 'border-brand-100 bg-brand-50 text-brand-800' : 'border-transparent text-gray-600 hover:bg-gray-50'}`}>
              <Icon size={16} /> {label.replace('🚚 ', '')}
            </NavLink>
          ))}
        </nav>
        <main className="flex-1 min-w-0 overflow-y-auto">
          <div className="mx-auto max-w-6xl px-4 py-5 sm:px-6 sm:py-7 lg:px-8">{children}</div>
        </main>
      </div>
      <AssistantPanel />
    </div>
  )
}
