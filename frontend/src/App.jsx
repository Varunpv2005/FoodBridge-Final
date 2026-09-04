import { lazy, Suspense } from 'react'
import { Routes, Route, Navigate } from 'react-router-dom'
import { useAuth } from './context/AuthContext'
import Layout from './components/Layout'
import Login from './pages/Login'
import Register from './pages/Register'

const DonorDashboard = lazy(() => import('./pages/donor/DonorDashboard'))
const NewDonation = lazy(() => import('./pages/donor/NewDonation'))
const NgoDashboard = lazy(() => import('./pages/ngo/NgoDashboard'))
const VolunteerDashboard = lazy(() => import('./pages/volunteer/VolunteerDashboard'))
const AdminOverview = lazy(() => import('./pages/admin/AdminOverview'))
const LiveMap = lazy(() => import('./pages/admin/LiveMap'))
const AnomalyQueue = lazy(() => import('./pages/admin/AnomalyQueue'))
const UsersTable = lazy(() => import('./pages/admin/UsersTable'))
const MlPlayground = lazy(() => import('./pages/admin/MlPlayground'))
const EvaluationResults = lazy(() => import('./pages/admin/EvaluationResults'))

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
    <Suspense fallback={<div className="flex min-h-screen items-center justify-center bg-gray-50 px-6 text-sm text-gray-600" role="status">Opening your workspace…</div>}>
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
        <Route path="/admin/results" element={<Protected roles={['admin']}><EvaluationResults /></Protected>} />

        <Route path="*" element={<Navigate to={user ? `/${user.role}` : '/login'} replace />} />
      </Routes>
    </Suspense>
  )
}
