import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../../api/client'
import { PageHeader, ErrorBanner } from '../../components/UI'
import { Clock, MapPin, Camera } from 'lucide-react'

const STATUS_STYLE = {
  pending_quality_check: 'bg-gray-100 text-gray-600',
  rejected_quality: 'bg-red-100 text-red-700',
  pending_match: 'bg-amber-100 text-amber-700',
  matched: 'bg-blue-100 text-blue-700',
  assigned_volunteer: 'bg-indigo-100 text-indigo-700',
  picked_up: 'bg-indigo-100 text-indigo-700',
  delivered: 'bg-brand-100 text-brand-800',
  expired: 'bg-gray-200 text-gray-600',
  flagged_anomaly: 'bg-red-100 text-red-700',
}

function StatusBadge({ status }) {
  return (
    <span className={`text-xs font-medium px-2.5 py-1 rounded-full ${STATUS_STYLE[status] || 'bg-gray-100'}`}>
      {status.replaceAll('_', ' ')}
    </span>
  )
}

export default function DonorDashboard() {
  const [donations, setDonations] = useState([]);
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)

  const load = () => api.myDonations().then(setDonations).catch((e) => setError(e.message)).finally(() => setLoading(false))

  useEffect(() => {
    load()
    const t = setInterval(load, 8000)  // light polling for status changes
    return () => clearInterval(t)
  }, [])

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <PageHeader title="My Donations" subtitle="Track quality checks, NGO matches, and delivery status in real time." />
        <Link to="/donor/new" className="btn-primary shrink-0">+ New Donation</Link>
      </div>
      <ErrorBanner message={error} />

      {!loading && donations.length === 0 && (
        <div className="card text-center text-gray-400 py-12">
          No donations yet. <Link to="/donor/new" className="text-brand-700 font-medium">Create your first one</Link>.
        </div>
      )}

      <div className="space-y-3">
        {donations.map((d) => (
          <div key={d.id} className="card flex items-center gap-4">
            <div className="w-12 h-12 rounded-xl bg-gray-50 flex items-center justify-center shrink-0">
              <Camera size={18} className="text-gray-400" />
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 flex-wrap">
                <p className="font-medium text-gray-900 capitalize">{d.food_type} · {d.quantity_plates} plates</p>
                <StatusBadge status={d.status} />
              </div>
              <div className="flex items-center gap-4 text-xs text-gray-400 mt-1">
                <span className="flex items-center gap-1"><MapPin size={12} /> {d.pickup_address || `${d.pickup_lat.toFixed(3)}, ${d.pickup_lng.toFixed(3)}`}</span>
                {d.degradation_hours != null && (
                  <span className="flex items-center gap-1"><Clock size={12} /> {d.degradation_hours}h safe window</span>
                )}
              </div>
              {d.match_reason && <p className="text-xs text-gray-500 mt-1.5 italic">"{d.match_reason}"</p>}
            </div>
            {d.match_probability != null && (
              <div className="text-right shrink-0">
                <p className="text-lg font-semibold text-brand-700">{(d.match_probability * 100).toFixed(0)}%</p>
                <p className="text-[10px] text-gray-400">match score</p>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}
