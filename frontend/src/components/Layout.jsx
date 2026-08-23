import { NavLink, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import {
  LayoutDashboard, Camera, Package, Users, Truck, ShieldAlert,
  Leaf, LogOut, MapPin, MessageSquareText,
} from 'lucide-react'

const NAV_BY_ROLE = {
  donor: [
    { to: '/donor', label: 'My Donations', icon: Package, end: true },
    { to: '/donor/new', label: 'New Donation', icon: Camera },
  ],
  ngo: [
    { to: '/ngo', label: 'Incoming Donations', icon: Package, end: true },
  ],
  volunteer: [
    { to: '/volunteer', label: 'My Deliveries', icon: Truck, end: true },
  ],
  admin: [
    { to: '/admin', label: 'Overview', icon: LayoutDashboard, end: true },
    { to: '/admin/map', label: 'Live Map', icon: MapPin },
    { to: '/admin/anomalies', label: 'Anomaly Queue', icon: ShieldAlert },
    { to: '/admin/users', label: 'Users', icon: Users },
    { to: '/admin/ml', label: 'ML Playground', icon: MessageSquareText },
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
      <aside className="w-64 bg-white border-r border-gray-100 flex flex-col shrink-0">
        <div className="flex items-center gap-2 px-6 py-5 border-b border-gray-100">
          <div className="w-8 h-8 rounded-lg bg-brand-600 flex items-center justify-center">
            <Leaf size={18} className="text-white" />
          </div>
          <div>
            <p className="font-semibold text-gray-900 leading-tight">FoodBridge</p>
            <p className="text-[11px] text-gray-400 leading-tight capitalize">{user?.role} Console</p>
          </div>
        </div>
        <nav className="flex-1 px-3 py-4 space-y-1">
          {links.map(({ to, label, icon: Icon, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-colors ${
                  isActive ? 'bg-brand-50 text-brand-700' : 'text-gray-600 hover:bg-gray-50'
                }`
              }
            >
              <Icon size={17} />
              {label}
            </NavLink>
          ))}
        </nav>
        <div className="px-4 py-4 border-t border-gray-100">
          <div className="flex items-center justify-between px-2">
            <div className="min-w-0">
              <p className="text-sm font-medium text-gray-700 truncate">{user?.name}</p>
              <p className="text-[11px] text-gray-400 truncate">{user?.email}</p>
            </div>
            <button onClick={handleLogout} className="text-gray-400 hover:text-red-500 shrink-0 ml-2">
              <LogOut size={16} />
            </button>
          </div>
        </div>
      </aside>
      <main className="flex-1 min-w-0 overflow-y-auto">
        <div className="max-w-6xl mx-auto px-8 py-8">{children}</div>
      </main>
    </div>
  )
}
