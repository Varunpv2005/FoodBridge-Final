import { useEffect, useRef, useState } from 'react'
import { api } from '../../api/client'
import { PageHeader, ErrorBanner } from '../../components/UI'
import MapView from '../../components/MapView'
import { useTrackingSocket } from '../../hooks/useTrackingSocket'
import { useToast } from '../../context/ToastContext'

export default function LiveMap() {
  const { notify } = useToast()
  const [users, setUsers] = useState([])
  const [deliveries, setDeliveries] = useState([])
  const [error, setError] = useState('')
  const [liveOverrides, setLiveOverrides] = useState({})
  const connectionSeen = useRef(false)
  const { lastMessage: liveMsg, connected } = useTrackingSocket('admin')

  const load = () => {
    api.allUsers().then(setUsers).catch((e) => setError(e.message))
    api.allDeliveries().then((items) => {
      setDeliveries(items)
      setLiveOverrides((positions) => items.reduce((next, item) => {
        if (Number.isFinite(item.latest_location_lat) && Number.isFinite(item.latest_location_lng)) {
          next[item.volunteer_id] = [item.latest_location_lat, item.latest_location_lng]
        }
        return next
      }, { ...positions }))
    }).catch(() => {})
  }

  useEffect(() => {
    load()
  }, [])

  useEffect(() => {
    if (connected) {
      if (connectionSeen.current) notify('Live tracking restored', { key: 'admin:reconnected', tone: 'info' })
      connectionSeen.current = true
    }
  }, [connected])

  useEffect(() => {
    if (liveMsg && liveMsg.type !== 'location_update') load()
    if (liveMsg && liveMsg.volunteer_id && Number.isFinite(liveMsg.lat)) {
      setLiveOverrides((prev) => ({ ...prev, [liveMsg.volunteer_id]: [liveMsg.lat, liveMsg.lng] }))
    }
    const messages = {
      delivery_assigned: 'Volunteer assigned successfully',
      arrival_detected: 'Volunteer has arrived at the stop',
      stop_completed: 'Stop completed successfully',
      delivery_completed: 'Delivery completed successfully',
      route_deviation: 'Route deviation detected',
      route_recovered: 'Live route restored',
    }
    const message = messages[liveMsg?.type]
    if (message) notify(message, { key: `admin:${liveMsg.type}:${liveMsg.delivery_id || liveMsg.stop_id || liveMsg.timestamp}`, tone: liveMsg.type === 'route_deviation' ? 'warning' : 'success' })
  }, [liveMsg])

  const markers = users.map((u) => {
    const pos = liveOverrides[u.id] || [u.lat, u.lng]
    return { id: u.id, live: Boolean(liveOverrides[u.id]), lat: pos[0], lng: pos[1], type: u.role, popup: `${u.name} (${u.role})` }
  })

  const activeRoutes = deliveries.filter((d) => d.status === 'en_route' || d.status === 'planned')
  const urgentRoutes = activeRoutes.filter((d) => Number(d.urgent_stop_count) > 0 || Number(d.expected_late_stop_count) > 0)

  return (
    <div className="space-y-6 pb-8">
      <PageHeader title="Live Operations Map" subtitle="Every donor, NGO, and volunteer, plus active delivery routes — updates in real time via WebSocket." />
      <ErrorBanner message={error} />

      <div className="grid gap-4 md:grid-cols-3">
        <div className="rounded-2xl border border-gray-200 bg-white p-4 shadow-sm">
          <p className="text-xs font-semibold uppercase tracking-[0.12em] text-gray-500">Active routes</p>
          <p className="mt-3 text-3xl font-semibold text-gray-900">{activeRoutes.length}</p>
        </div>
        <div className="rounded-2xl border border-gray-200 bg-white p-4 shadow-sm">
          <p className="text-xs font-semibold uppercase tracking-[0.12em] text-gray-500">Urgent routes</p>
          <p className="mt-3 text-3xl font-semibold text-amber-700">{urgentRoutes.length}</p>
        </div>
        <div className="rounded-2xl border border-gray-200 bg-white p-4 shadow-sm">
          <p className="text-xs font-semibold uppercase tracking-[0.12em] text-gray-500">Tracked users</p>
          <p className="mt-3 text-3xl font-semibold text-brand-700">{users.length}</p>
        </div>
      </div>

      <div className="rounded-3xl border border-gray-200 bg-white p-4 shadow-sm">
        <div className="mb-4 flex flex-wrap gap-4 text-xs text-gray-500">
          <span className="flex items-center gap-1.5"><span className="inline-block h-2.5 w-2.5 rounded-full bg-amber-500" /> Donor</span>
          <span className="flex items-center gap-1.5"><span className="inline-block h-2.5 w-2.5 rounded-full bg-brand-600" /> NGO</span>
          <span className="flex items-center gap-1.5"><span className="inline-block h-2.5 w-2.5 rounded-full bg-blue-600" /> Volunteer</span>
        </div>

        <MapView
          markers={markers}
          routes={activeRoutes.map((delivery) => ({ id: delivery.id, route: delivery.route_geojson }))}
          legendVariant="platform"
          height={560}
          zoom={12}
        />
      </div>

      {activeRoutes.length > 0 && (
        <div className="rounded-3xl border border-gray-200 bg-white p-5 shadow-sm">
          <h3 className="text-xl font-semibold text-gray-900">Active routes</h3>
          <div className="mt-4 space-y-3 text-sm text-gray-600">
            {activeRoutes.map((d) => (
              <div key={d.id} className="flex items-center justify-between gap-3 rounded-2xl border border-gray-100 bg-gray-50 px-3 py-2">
                <div>
                  <p className="font-medium text-gray-900">#{d.id.slice(0, 8)} · {d.stops.length} stops</p>
                  <p className="mt-1 text-xs text-gray-500">{d.status === 'en_route' ? 'Currently delivering' : 'Planned route'}</p>
                </div>
                <div className="text-right">
                  <p className="font-medium text-gray-900">{d.total_distance_km} km</p>
                  <p className="text-xs text-gray-500">{d.status}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
