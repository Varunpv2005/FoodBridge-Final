import { useEffect, useState } from 'react'
import { api } from '../../api/client'
import { PageHeader, ErrorBanner, StatBadge } from '../../components/UI'

export default function AdminOverview() {
  const [overview, setOverview] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    const load = () => api.overview().then(setOverview).catch((e) => setError(e.message))
    load()
    const t = setInterval(load, 8000)
    return () => clearInterval(t)
  }, [])

  return (
    <div>
      <PageHeader title="Platform Overview" subtitle="Live totals across donors, NGOs, volunteers, and the ML decision pipeline." />
      <ErrorBanner message={error} />

      {overview && (
        <>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
            <StatBadge label="Total donations" value={overview.totals.donations} />
            <StatBadge label="Total deliveries" value={overview.totals.deliveries} />
            <StatBadge label="Active (en route)" value={overview.active_deliveries} tone="good" />
            <StatBadge label="Anomalies pending" value={overview.anomalies_pending} tone={overview.anomalies_pending > 0 ? 'bad' : 'default'} />
          </div>

          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
            <StatBadge label="Donors" value={overview.totals.donors} />
            <StatBadge label="NGOs" value={overview.totals.ngos} />
            <StatBadge label="Volunteers" value={overview.totals.volunteers} />
            <StatBadge label="Plates delivered" value={overview.total_plates_delivered} tone="good" />
          </div>

          <div className="card">
            <h3 className="font-semibold text-gray-900 mb-3">Donations by status</h3>
            <div className="space-y-2">
              {Object.entries(overview.donations_by_status).map(([status, count]) => (
                <div key={status} className="flex items-center justify-between text-sm">
                  <span className="text-gray-600 capitalize">{status.replaceAll('_', ' ')}</span>
                  <span className="font-medium text-gray-900">{count}</span>
                </div>
              ))}
            </div>
          </div>
        </>
      )}
    </div>
  )
}
