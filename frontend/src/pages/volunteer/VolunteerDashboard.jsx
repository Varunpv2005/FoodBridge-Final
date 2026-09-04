import { useEffect, useRef, useState } from 'react'
import { api } from '../../api/client'
import { ErrorBanner, LoadingState, EmptyState } from '../../components/UI'
import MapView from '../../components/MapView'
import { useTrackingSocket } from '../../hooks/useTrackingSocket'
import { useAuth } from '../../context/AuthContext'
import { useToast } from '../../context/ToastContext'
import { Navigation, CheckCircle2, PlayCircle, Clock, MapPin, AlertTriangle, ArrowRight, Route, Check, BriefcaseBusiness } from 'lucide-react'

function formatArrival(value) {
  if (!value) return null
  const timestamp = value.endsWith('Z') ? value : `${value}Z`
  return new Date(timestamp).toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' })
}

function formatFoodWindow(minutes) {
  if (minutes == null) return null
  if (minutes < 0) return 'Food window may be exceeded'
  const hours = Math.floor(minutes / 60)
  const remainingMinutes = Math.round(minutes % 60)
  if (!hours) return `${remainingMinutes}m remaining`
  return `${hours}h ${remainingMinutes}m remaining`
}

function formatDistance(value) {
  if (value == null || Number.isNaN(Number(value))) return 'Distance unavailable'
  return `${Number(value).toFixed(1)} km`
}

function formatMinutes(value) {
  if (value == null || Number.isNaN(Number(value))) return 'Travel time unavailable'
  return `About ${Number(value).toFixed(0)} min`
}

function distanceMeters(first, second) {
  if (!first || !second) return null
  const earthRadius = 6371000
  const latitudeDelta = (second[0] - first[0]) * Math.PI / 180
  const longitudeDelta = (second[1] - first[1]) * Math.PI / 180
  const a = Math.sin(latitudeDelta / 2) ** 2
    + Math.cos(first[0] * Math.PI / 180) * Math.cos(second[0] * Math.PI / 180) * Math.sin(longitudeDelta / 2) ** 2
  return earthRadius * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a))
}

function getDeliveryStatusMeta(delivery) {
  const status = delivery?.status || 'planned'
  const base = {
    en_route: { label: 'EN ROUTE', badge: 'bg-brand-100 text-brand-800 border-brand-200', banner: '🚚 You are currently delivering', helper: 'Continue your active route.', accent: 'brand' },
    delayed: { label: 'DELAYED', badge: 'bg-amber-100 text-amber-800 border-amber-200', banner: '⏱ Delivery is delayed', helper: 'Check the route and urgent stops first.', accent: 'warn' },
    planned: { label: 'NOT STARTED', badge: 'bg-slate-100 text-slate-700 border-slate-200', banner: '📌 Ready to start', helper: 'Start delivery when you are ready to leave.', accent: 'neutral' },
    completed: { label: 'COMPLETED', badge: 'bg-emerald-100 text-emerald-800 border-emerald-200', banner: '✓ Completed', helper: 'This route has been finished.', accent: 'good' },
    picked_up: { label: 'IN PROGRESS', badge: 'bg-indigo-100 text-indigo-800 border-indigo-200', banner: '🚚 Route in progress', helper: 'Keep moving to the next stop.', accent: 'brand' },
  }
  return base[status] || base.planned
}

function getUrgentStops(delivery) {
  const count = Number(delivery?.urgent_stop_count)
  if (!Number.isNaN(count) && count > 0) return count
  if (!Array.isArray(delivery?.stops)) return 0
  return delivery.stops.filter((stop) => {
    const urgency = (stop?.urgency || '').toString().toLowerCase()
    return urgency === 'high' || urgency === 'urgent' || urgency === 'critical'
  }).length
}

function getExpectedLateStops(delivery) {
  const count = Number(delivery?.expected_late_stop_count)
  if (!Number.isNaN(count) && count > 0) return count
  if (!Array.isArray(delivery?.stops)) return 0
  return delivery.stops.filter((stop) => Number(stop?.lateness_minutes) > 0 || Number(stop?.remaining_food_window_minutes) < 0).length
}

function sortDeliveries(items) {
  const priority = { en_route: 0, delayed: 1, planned: 2, picked_up: 3, completed: 4 }
  return [...items].sort((a, b) => (priority[a?.status] ?? 99) - (priority[b?.status] ?? 99))
}

function DeliveryCard({ delivery, onChanged }) {
  const { user } = useAuth()
  const { notify } = useToast()
  const [expanded, setExpanded] = useState(false)
  const [trackingActive, setTrackingActive] = useState(delivery.status === 'en_route')
  const [starting, setStarting] = useState(false)
  const [actionError, setActionError] = useState('')
  const [deviationNotice, setDeviationNotice] = useState('')
  const [completingStop, setCompletingStop] = useState(null)
  const gpsWatchRef = useRef(null)
  const lastLocationSentRef = useRef(null)
  const [gpsActive, setGpsActive] = useState(false)
  const { lastMessage: liveMsg, send: sendLocation, connected } = useTrackingSocket(
    trackingActive ? delivery.id : null
  )
  const [liveVolunteerPos, setLiveVolunteerPos] = useState(
    delivery.latest_location_lat != null && delivery.latest_location_lng != null
      ? [delivery.latest_location_lat, delivery.latest_location_lng]
      : null
  )
  const gpsFixReceivedRef = useRef(false)

  const meta = getDeliveryStatusMeta(delivery)
  const urgentStops = getUrgentStops(delivery)
  const expectedLateStops = getExpectedLateStops(delivery)
  const currentStop = delivery.stops.find((stop) => stop.status !== 'completed')
  const remainingStops = delivery.stops.filter((stop) => stop.status !== 'completed').length

  useEffect(() => {
    setGpsActive(connected && gpsFixReceivedRef.current)
  }, [connected])

  useEffect(() => {
    if (liveMsg && liveMsg.type === 'location_update' && Number.isFinite(liveMsg.lat)) {
      setLiveVolunteerPos([liveMsg.lat, liveMsg.lng])
    }
    if (liveMsg?.type === 'route_deviation') {
      setDeviationNotice('Route deviation detected. Recalculating your route…')
      onChanged()
    }
    if (liveMsg?.type === 'route_recovered') {
      setDeviationNotice('Route recalculated from your current location.')
      onChanged()
    }
    const messages = {
      arrival_detected: 'Volunteer has arrived at the stop',
      stop_completed: 'Stop completed successfully',
      delivery_completed: 'Delivery completed successfully',
      route_deviation: 'Route deviation detected',
      route_recovered: 'Live route restored',
    }
    const message = messages[liveMsg?.type]
    if (message) notify(message, { key: `volunteer:${liveMsg.type}:${liveMsg.delivery_id || liveMsg.stop_id || liveMsg.timestamp}`, tone: liveMsg.type === 'route_deviation' ? 'warning' : 'success' })
  }, [liveMsg])

  useEffect(() => () => {
    if (gpsWatchRef.current !== null) {
      navigator.geolocation.clearWatch(gpsWatchRef.current)
      gpsWatchRef.current = null
    }
  }, [])

  const startGps = () => {
    if (!navigator.geolocation) {
      alert('GPS is not supported by this browser.')
      return
    }

    gpsWatchRef.current = navigator.geolocation.watchPosition(
      async (position) => {
        const lat = position.coords.latitude
        const lng = position.coords.longitude
        const current = [lat, lng]
        setLiveVolunteerPos(current)
        const now = Date.now()
        const previous = lastLocationSentRef.current
        if (previous && now - previous.timestamp < 5000 && distanceMeters(previous.position, current) < 20) return
        lastLocationSentRef.current = { position: current, timestamp: now }

        try {
          const sent = sendLocation({
            type: 'location_update',
            latitude: lat,
            longitude: lng,
            lat,
            lng,
            accuracy: position.coords.accuracy,
            timestamp: new Date(position.timestamp).toISOString(),
            delivery_id: delivery.id,
            volunteer_id: user.id,
          })
          gpsFixReceivedRef.current = true
          setGpsActive(sent && connected)
        } catch (error) {
          console.error('Failed to send GPS location:', error)
        }
      },
      (error) => {
        console.error('GPS error:', error)
        setGpsActive(false)

        if (error.code === 1) {
          alert('Location permission is required for live tracking.')
        } else if (error.code === 2) {
          alert('Your location could not be determined.')
        } else if (error.code === 3) {
          alert('Location request timed out.')
        }
      },
      {
        enableHighAccuracy: true,
        maximumAge: 5000,
        timeout: 10000,
      }
    )
  }

  useEffect(() => {
    if (!trackingActive || delivery.status === 'completed') return undefined
    startGps()
    return () => {
      if (gpsWatchRef.current !== null) {
        navigator.geolocation.clearWatch(gpsWatchRef.current)
        gpsWatchRef.current = null
      }
    }
  }, [trackingActive, delivery.status])

  const start = async () => {
    setStarting(true)
    try {
      await api.startDelivery(delivery.id)
      setTrackingActive(true)
      onChanged()
    } catch (e) {
      setActionError(e.message)
    } finally {
      setStarting(false)
    }
  }

  const arrive = async (stopId) => {
    setCompletingStop(stopId)
    setActionError('')
    try {
      await api.arriveStop(stopId)
      onChanged()
    } catch (e) {
      setActionError(e.message)
    } finally {
      setCompletingStop(null)
    }
  }

  const actionLabel = delivery.status === 'en_route' ? 'Continue Delivery' : delivery.status === 'completed' ? 'View Summary' : 'Start Delivery'
  const title = `Delivery Route #${(delivery.id || '').slice(0, 8).toUpperCase()}`
  const currentStopPosition = currentStop ? [currentStop.lat, currentStop.lng] : null
  const distanceToCurrentStop = distanceMeters(liveVolunteerPos, currentStopPosition)
  const openNavigation = () => {
    if (!currentStop) return
    window.open(`https://www.google.com/maps/dir/?api=1&destination=${currentStop.lat},${currentStop.lng}&travelmode=driving`, '_blank', 'noopener,noreferrer')
  }

  const markers = delivery.stops.map((s, index) => ({
    lat: s.lat, lng: s.lng, type: s.stop_type === 'pickup' ? 'pickup' : index === delivery.stops.length - 1 ? 'dropoff' : 'stop', glyph: String(s.sequence + 1), popup: `${s.sequence + 1}. ${s.stop_type === 'pickup' ? 'Pickup' : index === delivery.stops.length - 1 ? 'Final drop-off' : 'Delivery stop'} · ${s.status}`,
  }))
  if (liveVolunteerPos) markers.push({ id: `volunteer-${delivery.id}`, live: true, lat: liveVolunteerPos[0], lng: liveVolunteerPos[1], type: 'volunteer', popup: 'You are here (live)' })

  return (
    <article className={`rounded-2xl border bg-white shadow-sm transition ${delivery.status === 'en_route' ? 'border-brand-200 shadow-brand-100/50' : 'border-gray-200'} ${delivery.status === 'completed' ? 'opacity-90' : ''}`}>
      {actionError && <div className="border-b border-red-100 bg-red-50 px-4 py-3 text-sm text-red-700">{actionError}</div>}

      <div className="p-4 sm:p-5">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div className="min-w-0">
            <div className="mb-2 flex flex-wrap items-center gap-2">
              <span className={`inline-flex items-center rounded-full border px-2.5 py-1 text-[10px] font-semibold tracking-[0.12em] ${meta.badge}`}>
                {meta.label}
              </span>
              {delivery.status === 'en_route' && (
                <span className="inline-flex items-center gap-1 rounded-full bg-brand-50 px-2 py-1 text-[10px] font-medium text-brand-700">
                  <Route size={12} /> Active
                </span>
              )}
            </div>

            <h3 className="text-lg font-semibold text-gray-900">{title}</h3>
            <div className="mt-3 flex flex-wrap items-center gap-2 text-sm text-gray-600">
              <span className="inline-flex items-center gap-1.5 rounded-full border border-gray-200 bg-gray-50 px-2.5 py-1">
                <MapPin size={14} /> {delivery.stops.length} stops
              </span>
              <span className="inline-flex items-center gap-1.5 rounded-full border border-gray-200 bg-gray-50 px-2.5 py-1">
                <Route size={14} /> {formatDistance(delivery.total_distance_km)}
              </span>
              <span className="inline-flex items-center gap-1.5 rounded-full border border-gray-200 bg-gray-50 px-2.5 py-1">
                <Clock size={14} /> {formatMinutes(delivery.estimated_travel_minutes)}
              </span>
            </div>
          </div>

          <button
            type="button"
            onClick={delivery.status === 'completed' ? () => setExpanded((value) => !value) : () => setExpanded((value) => !value)}
            className={`inline-flex items-center justify-center rounded-xl px-4 py-2.5 text-sm font-semibold transition ${delivery.status === 'en_route' ? 'bg-brand-600 text-white hover:bg-brand-700' : delivery.status === 'completed' ? 'bg-gray-100 text-gray-700 hover:bg-gray-200' : 'bg-slate-900 text-white hover:bg-slate-800'}`}
          >
            {delivery.status === 'completed' ? 'View Summary' : delivery.status === 'en_route' ? 'Continue Delivery' : 'Start Delivery'}
          </button>
        </div>

        {delivery.status === 'en_route' && (
          <div className="mt-4 rounded-xl border border-brand-200 bg-brand-50 px-3 py-2 text-sm text-brand-800">
            <div className="flex items-center gap-2 font-medium">
              <span>🚚</span>
              <span>You are currently delivering</span>
            </div>
            <p className="mt-1 text-brand-700">Continue your active route.</p>
          </div>
        )}

        {deviationNotice && delivery.status !== 'completed' && (
          <div className="mt-4 rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800" role="status">
            <div className="flex items-center gap-2 font-medium"><AlertTriangle size={16} /> {deviationNotice}</div>
          </div>
        )}

        {(urgentStops > 0 || expectedLateStops > 0) && (
          <div className="mt-4 space-y-2">
            {urgentStops > 0 && (
              <div className="flex items-center gap-2 rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800">
                <AlertTriangle size={16} />
                <span>⚠️ {urgentStops} urgent stops</span>
              </div>
            )}
            {expectedLateStops > 0 && (
              <div className="flex items-center gap-2 rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800">
                <Clock size={16} />
                <span>⏱ {expectedLateStops} stops may be late</span>
              </div>
            )}
          </div>
        )}

        {delivery.status === 'completed' && (
          <div className="mt-4 rounded-xl border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-800">
            <div className="flex items-center gap-2 font-medium">
              <Check size={16} />
              <span>✓ Completed</span>
            </div>
            <p className="mt-1 text-emerald-700">{delivery.stops.length} stops • {formatDistance(delivery.total_distance_km)} • {formatMinutes(delivery.estimated_travel_minutes)}</p>
          </div>
        )}

        {expanded && (
          <div className="mt-5 space-y-4 border-t border-gray-100 pt-4">
            <div className="grid gap-3 sm:grid-cols-2 text-sm text-gray-600">
              <div className="rounded-xl bg-gray-50 p-3">
                <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-gray-500">Current task</p>
                <p className="mt-1 font-medium text-gray-900">{currentStop ? `${currentStop.stop_type === 'pickup' ? 'Pick up' : 'Deliver'} the next stop` : 'Route complete'}</p>
              </div>
              <div className="rounded-xl bg-gray-50 p-3">
                <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-gray-500">Remaining</p>
                <p className="mt-1 font-medium text-gray-900">{remainingStops} stops left</p>
              </div>
            </div>

            {distanceToCurrentStop != null && distanceToCurrentStop <= 100 && currentStop && (
              <div className="rounded-xl border border-brand-200 bg-brand-50 px-3 py-2 text-sm text-brand-800">
                You&apos;re near the {currentStop.stop_type === 'pickup' ? 'pickup' : 'delivery'} location. Confirm the stop when ready.
              </div>
            )}

            <div className="rounded-xl border border-gray-200 bg-gray-50 p-3">
              <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
                <div>
                  <p className="text-sm font-semibold text-gray-900">Live route</p>
                  <p className="mt-1 text-xs text-gray-500">Pickup, drop-off stops, and your current position</p>
                </div>
                <span className={`rounded-full px-2.5 py-1 text-[11px] font-semibold ${connected ? 'bg-emerald-100 text-emerald-700' : 'bg-amber-100 text-amber-700'}`}>
                  {connected ? 'Live connection' : 'Reconnecting'}
                </span>
              </div>
              <MapView markers={markers} route={delivery.route_geojson} routeError={delivery.route_error} height={360} />
              {delivery.route_error && <p className="mt-2 text-xs text-red-600">Route unavailable. Stop locations remain available.</p>}
              {!liveVolunteerPos && delivery.status === 'en_route' && <p className="mt-2 text-xs text-gray-500">Waiting for a real GPS position from this device.</p>}
            </div>

            <div className="space-y-2">
              <div className="flex items-center justify-between gap-3">
                <p className="text-sm font-semibold text-gray-900">Stops</p>
                <p className="text-xs text-gray-500">{remainingStops} remaining</p>
              </div>
              {delivery.stops.map((s) => (
                <div key={s.id} className={`flex items-start justify-between gap-3 rounded-xl border px-3 py-2 ${s.id === currentStop?.id ? 'border-brand-300 bg-brand-50' : 'border-gray-200 bg-white'}`}>
                  <div className="min-w-0">
                    <p className="text-sm font-medium text-gray-900">
                      {s.sequence + 1}. {s.stop_type === 'pickup' ? 'Pickup' : 'Drop-off'}
                    </p>
                    <p className="mt-1 text-xs text-gray-500">
                      {s.food_type || 'Donation'}{s.quantity_plates ? ` • ${s.quantity_plates} plates` : ''}
                    </p>
                    {(s.estimated_arrival || s.remaining_food_window_minutes != null || s.urgency) && (
                      <p className="mt-1 text-xs text-gray-500">
                        {s.estimated_arrival && `ETA ${formatArrival(s.estimated_arrival)}`}
                        {s.remaining_food_window_minutes != null && ` • ${formatFoodWindow(s.remaining_food_window_minutes)}`}
                        {s.urgency && ` • ${s.urgency.toUpperCase()} urgency`}
                      </p>
                    )}
                  </div>
                  <div className="flex items-center gap-2">
                    <span className={`rounded-full px-2 py-1 text-[10px] font-semibold ${s.status === 'completed' ? 'bg-emerald-100 text-emerald-700' : 'bg-slate-100 text-slate-600'}`}>
                      {s.status === 'completed' ? 'Done' : 'Open'}
                    </span>
                    {s.id === currentStop?.id && delivery.status !== 'planned' && (
                      <button onClick={() => arrive(s.id)} disabled={completingStop === s.id} className="inline-flex h-8 w-8 items-center justify-center rounded-lg bg-brand-600 text-white hover:bg-brand-700 disabled:opacity-50" aria-label="Mark stop complete">
                        <CheckCircle2 size={16} />
                      </button>
                    )}
                  </div>
                </div>
              ))}
            </div>

            {currentStop && delivery.status !== 'completed' && (
              <button type="button" onClick={openNavigation} className="inline-flex w-full items-center justify-center gap-2 rounded-xl border border-gray-200 px-4 py-2.5 text-sm font-semibold text-gray-700 transition hover:bg-gray-50">
                <Navigation size={16} /> Open navigation to current stop
              </button>
            )}

            {delivery.status === 'planned' && (
              <button onClick={start} disabled={starting} className="btn-primary flex w-full items-center justify-center gap-2">
                <PlayCircle size={16} /> {starting ? 'Starting…' : 'Start Delivery'}
              </button>
            )}

            {delivery.status === 'en_route' && (
              <p className="flex items-center gap-2 text-xs text-gray-500">
                <Navigation size={12} className="text-brand-600" />
                {connected ? 'Live tracking is active.' : 'Connecting live tracking…'}
              </p>
            )}

            {gpsActive && (
              <p className="text-xs font-medium text-green-700">● Real GPS location is being shared</p>
            )}
          </div>
        )}
      </div>
    </article>
  )
}

export default function VolunteerDashboard() {
  const { user } = useAuth()
  const [deliveries, setDeliveries] = useState([])
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [loading, setLoading] = useState(true)
  const { notify } = useToast()

  const load = () => api.myDeliveries().then(setDeliveries).catch((e) => setError(e.message)).finally(() => setLoading(false))

  useEffect(() => { load() }, [])

  const { lastMessage, connected } = useTrackingSocket(user ? `volunteer:${user.id}` : null)

  useEffect(() => {
    if (connected) load()
  }, [connected])

  useEffect(() => {
    if (lastMessage && lastMessage.type !== 'location_update') {
      load()
      if (lastMessage.type === 'delivery_assigned') {
        setNotice(`New delivery assigned: #${lastMessage.delivery_id.slice(0, 8)}`)
        notify('Volunteer assigned successfully', { key: `volunteer:assigned:${lastMessage.delivery_id}` })
      }
    }
  }, [lastMessage])

  const summary = {
    active: deliveries.filter((d) => d.status === 'en_route').length,
    totalStops: deliveries.reduce((count, d) => count + (Array.isArray(d.stops) ? d.stops.length : 0), 0),
    urgent: deliveries.reduce((count, d) => count + getUrgentStops(d), 0),
    completed: deliveries.filter((d) => d.status === 'completed').length,
  }

  const sortedDeliveries = sortDeliveries(deliveries)
  const todayLabel = new Date().toLocaleDateString([], { weekday: 'long', month: 'short', day: 'numeric' })

  return (
    <div className="space-y-6 pb-8">
      <header className="rounded-3xl border border-gray-200 bg-white p-5 shadow-sm sm:p-6">
        <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
          <div>
            <p className="text-sm font-medium uppercase tracking-[0.12em] text-brand-700">Volunteer Console</p>
            <h1 className="mt-2 text-3xl font-semibold tracking-tight text-gray-900">Good day, {user?.name?.split(' ')[0] || 'Volunteer'} 👋</h1>
            <p className="mt-2 text-sm text-gray-600">Here’s what you need to know about your deliveries today.</p>
          </div>
          <div className="rounded-2xl border border-brand-100 bg-brand-50 px-4 py-3 text-sm text-brand-800">
            <div className="flex items-center gap-2 font-medium">
              <BriefcaseBusiness size={16} />
              <span>{todayLabel}</span>
            </div>
          </div>
        </div>
      </header>

      <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <div className="rounded-2xl border border-gray-200 bg-white p-4 shadow-sm">
          <p className="text-xs font-semibold uppercase tracking-[0.12em] text-gray-500">Active Deliveries</p>
          <p className="mt-3 text-3xl font-semibold text-gray-900">{summary.active}</p>
        </div>
        <div className="rounded-2xl border border-gray-200 bg-white p-4 shadow-sm">
          <p className="text-xs font-semibold uppercase tracking-[0.12em] text-gray-500">Total Stops</p>
          <p className="mt-3 text-3xl font-semibold text-gray-900">{summary.totalStops}</p>
        </div>
        <div className="rounded-2xl border border-gray-200 bg-white p-4 shadow-sm">
          <p className="text-xs font-semibold uppercase tracking-[0.12em] text-gray-500">Urgent Stops</p>
          <p className="mt-3 text-3xl font-semibold text-amber-700">{summary.urgent}</p>
        </div>
        <div className="rounded-2xl border border-gray-200 bg-white p-4 shadow-sm">
          <p className="text-xs font-semibold uppercase tracking-[0.12em] text-gray-500">Completed Deliveries</p>
          <p className="mt-3 text-3xl font-semibold text-emerald-700">{summary.completed}</p>
        </div>
      </section>

      <section className="rounded-3xl border border-gray-200 bg-white p-5 shadow-sm sm:p-6">
        <div className="mb-4 flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <h2 className="text-2xl font-semibold text-gray-900">Your Deliveries</h2>
            <p className="mt-1 text-sm text-gray-600">Deliveries assigned to you. Start an active delivery to begin sharing your live location.</p>
          </div>
        </div>

        <ErrorBanner message={error} />
        {notice && <div className="mb-4 rounded-xl border border-brand-100 bg-brand-50 px-4 py-3 text-sm text-brand-800">{notice}</div>}

        {loading ? <LoadingState label="Loading deliveries..." /> : sortedDeliveries.length === 0 ? (
          <EmptyState title="No active deliveries" message="New assignments will appear here." icon={Clock} />
        ) : (
          <div className="space-y-4">
            {sortedDeliveries.map((d) => <DeliveryCard key={d.id} delivery={d} onChanged={load} />)}
          </div>
        )}
      </section>
    </div>
  )
}
