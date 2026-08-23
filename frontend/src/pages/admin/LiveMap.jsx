import { useEffect, useState } from 'react'
import { api } from '../../api/client'
import { PageHeader, ErrorBanner } from '../../components/UI'
import MapView from '../../components/MapView'
import { useTrackingSocket } from '../../hooks/useTrackingSocket'

export default function LiveMap() {
  const [users, setUsers] = useState([])
  const [deliveries, setDeliveries] = useState([])
  const [error, setError] = useState('')
  const [liveOverrides, setLiveOverrides] = useState({})
  const liveMsg = useTrackingSocket('admin')

  const load = () => {
    api.allUsers().then(setUsers).catch((e) => setError(e.message))
    api.allDeliveries().then(setDeliveries).catch(() => {})
  }

  useEffect(() => {
    load()
    const t = setInterval(load, 10000)
    return () => clearInterval(t)
  }, [])

  useEffect(() => {
    if (liveMsg && liveMsg.volunteer_id && liveMsg.lat) {
      setLiveOverrides((prev) => ({ ...prev, [liveMsg.volunteer_id]: [liveMsg.lat, liveMsg.lng] }))
    }
  }, [liveMsg])

  const markers = users.map((u) => {
    const pos = liveOverrides[u.id] || [u.lat, u.lng]
    return { lat: pos[0], lng: pos[1], type: u.role, popup: `${u.name} (${u.role})` }
  })

  const activeRoutes = deliveries.filter((d) => d.status === 'en_route' || d.status === 'planned')

  return (
    <div>
      <PageHeader title="Live Operations Map" subtitle="Every donor, NGO, and volunteer, plus active delivery routes — updates in real time via WebSocket." />
      <ErrorBanner message={error} />

      <div className="flex gap-4 mb-4 text-xs text-gray-500">
        <span className="flex items-center gap-1"><span className="w-2.5 h-2.5 rounded-full bg-amber-500 inline-block" /> Donor</span>
        <span className="flex items-center gap-1"><span className="w-2.5 h-2.5 rounded-full bg-brand-600 inline-block" /> NGO</span>
        <span className="flex items-center gap-1"><span className="w-2.5 h-2.5 rounded-full bg-blue-600 inline-block" /> Volunteer</span>
      </div>

      <MapView markers={markers} height={560} zoom={12} />

      {activeRoutes.length > 0 && (
        <div className="card mt-6">
          <h3 className="font-semibold text-gray-900 mb-3">Active routes ({activeRoutes.length})</h3>
          <div className="space-y-2 text-sm text-gray-600">
            {activeRoutes.map((d) => (
              <div key={d.id} className="flex justify-between border-b border-gray-50 pb-2">
                <span>#{d.id.slice(0, 8)} · {d.stops.length} stops</span>
                <span>{d.total_distance_km} km · {d.status}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
