import { Routes, Route, Navigate } from 'react-router-dom'
import { useAuth } from './context/AuthContext'
import Layout from './components/Layout'
import Login from './pages/Login'
import Register from './pages/Register'
import DonorDashboard from './pages/donor/DonorDashboard'
import NewDonation from './pages/donor/NewDonation'
import NgoDashboard from './pages/ngo/NgoDashboard'
import VolunteerDashboard from './pages/volunteer/VolunteerDashboard'
import AdminOverview from './pages/admin/AdminOverview'
import LiveMap from './pages/admin/LiveMap'
import AnomalyQueue from './pages/admin/AnomalyQueue'
import UsersTable from './pages/admin/UsersTable'
import MlPlayground from './pages/admin/MlPlayground'

function Protected({ roles, children }) {
  const { user, loading } = useAuth()
  if (loading) return <div className="min-h-screen flex items-center justify-center text-gray-400">Loading…</div>
  if (!user) return <Navigate to="/login" replace />
  if (roles && !roles.includes(user.role)) return <Navigate to={`/${user.role}`} replace />
  return <Layout>{children}</Layout>
}

export default function App() {
  const { user } = useAuth()

  return (
    <Routes>
      <Route path="/login" element={user ? <Navigate to={`/${user.role}`} /> : <Login />} />
      <Route path="/register" element={user ? <Navigate to={`/${user.role}`} /> : <Register />} />

      <Route path="/donor" element={<Protected roles={['donor']}><DonorDashboard /></Protected>} />
      <Route path="/donor/new" element={<Protected roles={['donor']}><NewDonation /></Protected>} />

      <Route path="/ngo" element={<Protected roles={['ngo']}><NgoDashboard /></Protected>} />

      <Route path="/volunteer" element={<Protected roles={['volunteer']}><VolunteerDashboard /></Protected>} />

      <Route path="/admin" element={<Protected roles={['admin']}><AdminOverview /></Protected>} />
      <Route path="/admin/map" element={<Protected roles={['admin']}><LiveMap /></Protected>} />
      <Route path="/admin/anomalies" element={<Protected roles={['admin']}><AnomalyQueue /></Protected>} />
      <Route path="/admin/users" element={<Protected roles={['admin']}><UsersTable /></Protected>} />
      <Route path="/admin/ml" element={<Protected roles={['admin']}><MlPlayground /></Protected>} />

      <Route path="*" element={<Navigate to={user ? `/${user.role}` : '/login'} replace />} />
    </Routes>
  )
}
