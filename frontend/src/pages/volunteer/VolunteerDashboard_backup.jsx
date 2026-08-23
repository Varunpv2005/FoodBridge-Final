import { useEffect, useState } from 'react'
import { api } from '../../api/client'
import { PageHeader, ErrorBanner } from '../../components/UI'
import MapView from '../../components/MapView'
import { useTrackingSocket } from '../../hooks/useTrackingSocket'
import { Navigation, CheckCircle2, PlayCircle } from 'lucide-react'

function DeliveryCard({ delivery, onChanged }) {
  const [expanded, setExpanded] = useState(false)
  const liveMsg = useTrackingSocket(expanded ? delivery.id : null)
  const [liveVolunteerPos, setLiveVolunteerPos] = useState(null)

  useEffect(() => {
    if (liveMsg && liveMsg.lat) setLiveVolunteerPos([liveMsg.lat, liveMsg.lng])
  }, [liveMsg])

  const start = async () => {
    await api.startDelivery(delivery.id)
    onChanged()
  }
  const arrive = async (stopId) => {
    await api.arriveStop(stopId)
    onChanged()
  }

  const markers = delivery.stops.map((s) => ({
    lat: s.lat, lng: s.lng, type: s.stop_type === 'pickup' ? 'donor' : 'ngo',
    popup: `${s.stop_type} · ${s.status}`,
  }))
  if (liveVolunteerPos) markers.push({ lat: liveVolunteerPos[0], lng: liveVolunteerPos[1], type: 'volunteer', popup: 'You are here (live)' })

  return (
    <div className="card">
      <div className="flex items-center justify-between cursor-pointer" onClick={() => setExpanded((x) => !x)}>
        <div>
          <p className="font-medium text-gray-900">Delivery #{delivery.id.slice(0, 8)} · {delivery.stops.length} stops</p>
          <p className="text-xs text-gray-400">{delivery.total_distance_km} km total · status: {delivery.status}</p>
        </div>
        <span className="text-xs px-2 py-1 rounded-full bg-indigo-100 text-indigo-700">{delivery.status}</span>
      </div>

      {expanded && (
        <div className="mt-4 space-y-4">
          <div className="space-y-2">
            {delivery.stops.map((s) => (
              <div key={s.id} className="flex items-center justify-between text-sm border border-gray-100 rounded-lg px-3 py-2">
                <span className="capitalize">{s.sequence + 1}. {s.stop_type} {s.eta_minutes != null && `· ETA ${s.eta_minutes} min`}</span>
                <div className="flex items-center gap-2">
                  <span className={`text-xs px-2 py-0.5 rounded-full ${s.status === 'completed' ? 'bg-brand-100 text-brand-700' : 'bg-gray-100 text-gray-500'}`}>{s.status}</span>
                  {s.status !== 'completed' && delivery.status !== 'planned' && (
                    <button onClick={() => arrive(s.id)} className="text-brand-700"><CheckCircle2 size={16} /></button>
                  )}
                </div>
              </div>
            ))}
          </div>

          <MapView markers={markers} route={delivery.route_geojson} height={300} />

          {delivery.status === 'planned' && (
            <button onClick={start} className="btn-primary w-full flex items-center justify-center gap-2">
              <PlayCircle size={16} /> Start delivery (live GPS tracking begins)
            </button>
          )}
          {delivery.status === 'en_route' && (
            <p className="text-xs text-gray-400 flex items-center gap-1"><Navigation size={12} className="animate-pulse text-brand-600" /> Live tracking active — donor/NGO/admin can watch this delivery in real time.</p>
          )}
        </div>
      )}
    </div>
  )
}

export default function VolunteerDashboard() {
  const [deliveries, setDeliveries] = useState([])
  const [error, setError] = useState('')

  const load = () => api.myDeliveries().then(setDeliveries).catch((e) => setError(e.message))

  useEffect(() => {
    load()
    const t = setInterval(load, 6000)
    return () => clearInterval(t)
  }, [])

  return (
    <div>
      <PageHeader title="My Deliveries" subtitle="Multi-stop routes assigned to you. Start a delivery to begin live location sharing." />
      <ErrorBanner message={error} />

      {deliveries.length === 0 && <div className="card text-center text-gray-400 py-12">No deliveries assigned yet.</div>}

      <div className="space-y-3">
        {deliveries.map((d) => <DeliveryCard key={d.id} delivery={d} onChanged={load} />)}
      </div>
    </div>
  )
}
