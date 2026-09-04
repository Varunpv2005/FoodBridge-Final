import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../../api/client'
import { useAuth } from '../../context/AuthContext'
import { useToast } from '../../context/ToastContext'
import { useTrackingSocket } from '../../hooks/useTrackingSocket'
import { PageHeader, ErrorBanner, LoadingState, EmptyState } from '../../components/UI'
import { Clock, MapPin, Camera, Plus, PackageCheck, Truck, HeartHandshake } from 'lucide-react'
import MapView from '../../components/MapView'

const STATUS_STYLE = {
  pending_quality_check: 'bg-gray-100 text-gray-600',
  rejected_quality: 'bg-red-100 text-red-700',
  pending_match: 'bg-amber-100 text-amber-700',
  matched: 'bg-blue-100 text-blue-700',
  ngo_accepted: 'bg-emerald-100 text-emerald-700',
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

function formatUpdatedAt(value) {
  if (!value) return 'Waiting for first GPS update'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return 'Location timestamp unavailable'
  return `Updated ${date.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' })}`
}

function trackingLabel(donation) {
  if (donation.status === 'delivered' || donation.delivery_status === 'completed') return '✓ Delivered'
  if (donation.delivery_status === 'en_route') return '🟢 Volunteer is on the way'
  if (donation.status === 'picked_up') return 'Food picked up'
  if (donation.volunteer_id) return 'Volunteer assigned'
  return 'Waiting for volunteer assignment'
}

function trackingActionLabel(donation) {
  if (donation.status === 'delivered' || donation.delivery_status === 'completed') return 'View delivery'
  if (donation.delivery_status === 'en_route' || donation.status === 'picked_up') return 'Track live delivery'
  return 'Track donation'
}

const JOURNEY_STEPS = [
  ['created', 'Donation Created'],
  ['matched', 'NGO Request Sent'],
  ['accepted', 'NGO Accepted'],
  ['assigned', 'Volunteer Assigned'],
  ['picked_up', 'Picked Up'],
  ['in_transit', 'In Transit'],
  ['delivered', 'Delivered'],
]

function journeyStatus(donation) {
  if (donation.status === 'delivered' || donation.delivery_status === 'completed') return 'delivered'
  if (donation.delivery_status === 'en_route') return 'in_transit'
  if (donation.status === 'picked_up') return 'picked_up'
  if (donation.status === 'assigned_volunteer') return 'assigned'
  if (donation.status === 'ngo_accepted') return 'accepted'
  if (donation.status === 'matched' && donation.delivery_id) return 'accepted'
  if (donation.status === 'matched') return 'matched'
  return 'created'
}

function CompactJourney({ donation }) {
  const currentIndex = JOURNEY_STEPS.findIndex(([key]) => key === journeyStatus(donation))
  return (
    <div className="flex flex-wrap gap-1.5" aria-label="Donation journey">
      {JOURNEY_STEPS.map(([key, label], index) => (
        <span key={key} className={`rounded-full px-2 py-1 text-[11px] ${index === currentIndex ? 'bg-brand-100 font-semibold text-brand-800' : index < currentIndex ? 'bg-gray-100 text-gray-500' : 'bg-gray-50 text-gray-300'}`}>
          {index < currentIndex ? '✓ ' : ''}{label}
        </span>
      ))}
    </div>
  )
}

function relationshipLabel(donation) {
  const hasMatch = ['matched', 'ngo_accepted', 'assigned_volunteer', 'picked_up', 'delivered'].includes(donation.status)
  const hasAssignment = Boolean(donation.volunteer_id && donation.delivery_id)
  return {
    ngo: hasMatch ? (donation.matched_ngo_name || 'NGO matched') : 'Waiting for NGO match',
    volunteer: hasAssignment ? (donation.volunteer_name || 'Volunteer assigned') : 'Waiting for volunteer assignment',
  }
}

function requestSummary(donation) {
  const history = donation.ngo_request_history || []
  return history.length ? history.map((request) => `${request.ngo_name}: ${request.status}`).join(' · ') : null
}

function TrackVolunteerPanel({ donation, livePosition, connected, onClose }) {
  const hasRoute = Array.isArray(donation.delivery_route) && donation.delivery_route.length > 1
  const nextStop = donation.delivery_stops?.find((stop) => stop.status !== 'completed')
  const markers = [
    ...(donation.delivery_stops || []).map((stop, index) => ({
      id: `${donation.delivery_id}-stop-${index}`,
      lat: stop.lat,
      lng: stop.lng,
      type: stop.stop_type === 'pickup' ? 'pickup' : index === (donation.delivery_stops || []).length - 1 ? 'dropoff' : 'stop',
      glyph: String(index + 1),
      popup: stop.stop_type === 'pickup' ? 'Pickup location' : index === (donation.delivery_stops || []).length - 1 ? 'Final drop-off' : `Delivery stop ${index + 1}`,
    })),
    ...(livePosition ? [{
      id: `volunteer-${donation.delivery_id}`,
      live: true,
      lat: livePosition.lat,
      lng: livePosition.lng,
      type: 'volunteer',
      popup: 'Volunteer (live)',
    }] : []),
  ]

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-gray-950/40 p-4" role="dialog" aria-modal="true" aria-labelledby="track-volunteer-title">
      <div className="max-h-[calc(100vh-2rem)] w-full max-w-4xl overflow-y-auto rounded-2xl bg-white shadow-2xl">
        <div className="flex items-start justify-between gap-4 border-b border-gray-100 px-5 py-4 sm:px-6">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.14em] text-brand-700">Donation journey</p>
            <h2 id="track-volunteer-title" className="mt-1 text-xl font-semibold text-gray-900">Track Your Donation</h2>
            <p className="mt-1 text-sm text-gray-500 capitalize">{donation.food_type} · {donation.quantity_plates} plates</p>
          </div>
          <button type="button" onClick={onClose} className="rounded-lg px-3 py-2 text-sm font-medium text-gray-500 hover:bg-gray-100 hover:text-gray-800">Close</button>
        </div>

        <div className="grid gap-5 p-5 sm:p-6 lg:grid-cols-[minmax(0,1.4fr)_minmax(250px,0.6fr)]">
          <div className="min-w-0">
            <MapView markers={markers} route={hasRoute ? donation.delivery_route : null} height={420} />
            {!hasRoute && <p className="mt-2 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800">The route is not available yet. Pickup and destination markers remain visible.</p>}
            {!livePosition && donation.delivery_status === 'en_route' && (
              <p className="mt-2 text-xs text-gray-500">Waiting for the volunteer&apos;s first real GPS update.</p>
            )}
          </div>

          <div className="space-y-3">
            <div className="rounded-xl border border-brand-100 bg-brand-50 p-4">
              <p className="text-xs font-semibold uppercase tracking-[0.12em] text-brand-700">Status</p>
              <p className="mt-2 font-semibold text-gray-900">{trackingLabel(donation)}</p>
              <div className="mt-2"><StatusBadge status={donation.status} /></div>
            </div>
            <div className="rounded-xl border border-gray-200 p-4">
              <p className="text-sm font-semibold text-gray-900">Assigned to</p>
              <dl className="mt-3 space-y-2 text-sm">
                <div className="flex items-start justify-between gap-3"><dt className="text-gray-500">NGO</dt><dd className="text-right font-medium text-gray-900">{donation.matched_ngo_name || 'NGO matched'}</dd></div>
                <div className="flex items-start justify-between gap-3"><dt className="text-gray-500">Pickup</dt><dd className="max-w-[12rem] text-right font-medium text-gray-900">{donation.pickup_address || 'Location selected'}</dd></div>
                <div className="flex items-start justify-between gap-3"><dt className="text-gray-500">Destination</dt><dd className="text-right font-medium text-gray-900">{donation.matched_ngo_name || 'Destination unavailable'}</dd></div>
                <div className="flex items-start justify-between gap-3"><dt className="text-gray-500">Next step</dt><dd className="text-right font-medium capitalize text-gray-900">{nextStop ? `${nextStop.stop_type === 'pickup' ? 'Pickup' : 'Delivery stop'} pending` : 'Delivery complete'}</dd></div>
              </dl>
            </div>
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-1">
              <div className="rounded-xl border border-gray-200 p-3">
                <p className="text-sm text-gray-500">Volunteer</p>
                <p className="mt-1 text-sm font-medium text-gray-900">{donation.volunteer_name || 'Not assigned'}</p>
              </div>
              <div className="rounded-xl border border-gray-200 p-3">
                <p className="text-sm text-gray-500">Route distance</p>
                <p className="mt-1 text-sm font-medium text-gray-900">{donation.delivery_distance_km != null ? `${donation.delivery_distance_km} km` : 'Unavailable'}</p>
              </div>
              <div className="rounded-xl border border-gray-200 p-3">
                <p className="text-sm text-gray-500">ETA</p>
                <p className="mt-1 text-sm font-medium text-gray-900">{donation.delivery_eta_minutes != null ? `${Number(donation.delivery_eta_minutes).toFixed(0)} min` : 'Unavailable'}</p>
              </div>
              <div className="rounded-xl border border-gray-200 p-3">
                <p className="text-sm text-gray-500">Connection</p>
                <p className={`mt-1 text-sm font-medium ${connected ? 'text-emerald-700' : 'text-amber-700'}`}>{connected ? 'Live updates connected' : 'Reconnecting…'}</p>
              </div>
            </div>
            <p className="text-sm text-gray-500">{formatUpdatedAt(livePosition?.timestamp || donation.latest_location_timestamp)}</p>
            {donation.delivery_stops?.length > 0 && (
              <div className="rounded-xl border border-gray-200 bg-gray-50 p-4">
                <p className="text-sm font-semibold text-gray-900">Delivery stops</p>
                <div className="mt-3 space-y-2">
                  {donation.delivery_stops.map((stop, index) => (
                    <div key={`${stop.stop_type}-${index}`} className="flex items-start gap-3 text-sm">
                      <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-white font-semibold text-gray-700 shadow-sm">{index + 1}</span>
                      <div className="min-w-0">
                        <p className="font-medium capitalize text-gray-900">{stop.stop_type === 'pickup' ? 'Pickup' : index === donation.delivery_stops.length - 1 ? 'Final drop-off' : 'Delivery stop'}</p>
                        <p className="text-gray-500">{stop.status === 'completed' ? 'Completed' : stop.status || 'Pending'}</p>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

export default function DonorDashboard() {
  const { user } = useAuth()
  const { notify } = useToast()
  const [donations, setDonations] = useState([])
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)
  const [livePositions, setLivePositions] = useState({})
  const [expandedId, setExpandedId] = useState(null)
  const [matchDetailsId, setMatchDetailsId] = useState(null)
  const [trackingDonationId, setTrackingDonationId] = useState(null)
  const connectionSeen = useRef(false)

  const load = () => api.myDonations().then((items) => {
    setDonations(items)
    setLivePositions((positions) => items.reduce((next, item) => {
      if (item.delivery_id && Number.isFinite(item.latest_location_lat) && Number.isFinite(item.latest_location_lng)) {
        next[item.delivery_id] = { lat: item.latest_location_lat, lng: item.latest_location_lng, delivery_id: item.delivery_id }
      }
      return next
    }, { ...positions }))
  }).catch((e) => setError(e.message)).finally(() => setLoading(false))
  const { lastMessage: liveMsg, connected } = useTrackingSocket(user ? `donor:${user.id}` : null)

  useEffect(() => {
    load()
  }, [])

  useEffect(() => {
    if (connected) {
      load()
      if (connectionSeen.current) notify('Live tracking restored', { key: 'donor:reconnected', tone: 'info' })
      connectionSeen.current = true
    }
  }, [connected])

  useEffect(() => {
    if (liveMsg?.type === 'location_update' && liveMsg.delivery_id) {
      setLivePositions((positions) => ({ ...positions, [liveMsg.delivery_id]: liveMsg }))
    }
    if (liveMsg && liveMsg.type !== 'location_update') {
      load()
      const messages = {
        donation_available: 'Donation request sent to an NGO',
        donation_request: 'Donation request sent to the next suitable NGO',
        ngo_rejected: 'NGO declined; finding the next suitable NGO',
        ngo_accepted: 'NGO accepted your donation',
        donation_status: 'Donation status updated',
        delivery_assigned: 'Volunteer assigned successfully',
        arrival_detected: 'Volunteer has arrived at the stop',
        stop_completed: 'Stop completed successfully',
        delivery_completed: 'Delivery completed successfully',
        route_deviation: 'Route deviation detected',
        route_recovered: 'Live route restored',
      }
      const message = messages[liveMsg.type]
      if (message) notify(message, { key: `donor:${liveMsg.type}:${liveMsg.delivery_id || liveMsg.donation_id || liveMsg.timestamp}`, tone: liveMsg.type === 'route_deviation' ? 'warning' : 'success' })
    }
  }, [liveMsg])

  const summary = {
    total: donations.length,
    matched: donations.filter((d) => d.status === 'matched' || d.status === 'assigned_volunteer' || d.status === 'picked_up').length,
    active: donations.filter((d) => d.delivery_status === 'en_route').length,
    delivered: donations.filter((d) => d.status === 'delivered').length,
  }
  const trackingDonation = donations.find((donation) => donation.id === trackingDonationId)

  return (
    <div className="space-y-6 pb-8">
      <div className="flex flex-col gap-4 xl:flex-row xl:items-end xl:justify-between">
        <div className="flex-1">
          <PageHeader title="My Donations" subtitle="Follow every donation from quality check to delivery." />
        </div>
        <Link to="/donor/new" className="btn-primary inline-flex items-center justify-center gap-2 shrink-0">
          <Plus size={16} /> New Donation
        </Link>
      </div>

      <ErrorBanner message={error} />

      {loading && <LoadingState label="Loading donations..." />}
      {!loading && donations.length === 0 && <EmptyState title="No donations yet" message="Your submitted donations will appear here." icon={PackageCheck} />}

      {donations.length > 0 && (
        <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          <div className="rounded-2xl border border-gray-200 bg-white p-4 shadow-sm">
            <div className="flex items-center justify-between">
                  <p className="text-sm font-semibold uppercase tracking-[0.12em] text-gray-500">Total</p>
              <PackageCheck size={16} className="text-brand-600" />
            </div>
            <p className="mt-3 text-3xl font-semibold text-gray-900">{summary.total}</p>
          </div>
          <div className="rounded-2xl border border-gray-200 bg-white p-4 shadow-sm">
            <div className="flex items-center justify-between">
                  <p className="text-sm font-semibold uppercase tracking-[0.12em] text-gray-500">Matched</p>
              <HeartHandshake size={16} className="text-blue-600" />
            </div>
            <p className="mt-3 text-3xl font-semibold text-gray-900">{summary.matched}</p>
          </div>
          <div className="rounded-2xl border border-gray-200 bg-white p-4 shadow-sm">
            <div className="flex items-center justify-between">
                  <p className="text-sm font-semibold uppercase tracking-[0.12em] text-gray-500">In transit</p>
              <Truck size={16} className="text-brand-600" />
            </div>
            <p className="mt-3 text-3xl font-semibold text-gray-900">{summary.active}</p>
          </div>
          <div className="rounded-2xl border border-gray-200 bg-white p-4 shadow-sm">
            <div className="flex items-center justify-between">
                  <p className="text-sm font-semibold uppercase tracking-[0.12em] text-gray-500">Delivered</p>
              <PackageCheck size={16} className="text-emerald-600" />
            </div>
            <p className="mt-3 text-3xl font-semibold text-emerald-700">{summary.delivered}</p>
          </div>
        </section>
      )}

      <div className="space-y-4">
        {donations.map((d) => (
          <div key={d.id} className="rounded-2xl border border-gray-200 bg-white p-4 shadow-sm sm:p-5">
            <button type="button" onClick={() => setExpandedId(expandedId === d.id ? null : d.id)} className="w-full text-left">
              <div className="flex items-start gap-4">
                <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-gray-100 text-gray-500">
                  <Camera size={18} />
                </div>

                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <p className="font-semibold text-gray-900 capitalize">{d.food_type} · {d.quantity_plates} plates</p>
                    <StatusBadge status={d.status} />
                  </div>

                  <div className="mt-3"><CompactJourney donation={d} /></div>

                  <div className="mt-3 flex flex-wrap items-center gap-3 text-xs text-gray-500">
                    <span className="inline-flex items-center gap-1.5"><MapPin size={12} /> {d.pickup_address || `${d.pickup_lat.toFixed(3)}, ${d.pickup_lng.toFixed(3)}`}</span>
                    {d.degradation_hours != null && (
                      <span className="inline-flex items-center gap-1.5"><Clock size={12} /> {d.degradation_hours}h safe window</span>
                    )}
                  </div>

                  <div className="mt-3 grid gap-2 rounded-xl border border-gray-100 bg-gray-50 px-3 py-2 text-sm sm:grid-cols-2">
                    <p><span className="text-gray-500">NGO:</span> <span className="font-medium text-gray-900">{relationshipLabel(d).ngo}</span></p>
                    <p><span className="text-gray-500">Destination:</span> <span className="font-medium text-gray-900">{d.matched_ngo_name ? `${d.status === 'matched' ? 'Requested NGO: ' : 'NGO: '}${d.matched_ngo_name}` : d.status === 'matched' ? 'NGO request pending' : 'Not assigned'}</span></p>
                  </div>
                </div>

                {d.match_probability != null && (
                  <div className="shrink-0 text-right">
                    <p className="text-lg font-semibold text-brand-700">{(d.match_probability * 100).toFixed(0)}%</p>
                    <p className="text-[10px] uppercase tracking-[0.12em] text-gray-400">match</p>
                  </div>
                )}
              </div>
            </button>

            <div className="mt-4 flex flex-wrap items-center justify-between gap-3 border-t border-gray-100 pt-3">
              <div className="min-w-0 text-xs text-gray-500">
                {d.volunteer_name && <span className="font-medium text-gray-700">{d.volunteer_name}</span>}
                {d.volunteer_name && <span className="mx-2 text-gray-300">·</span>}
                <span className="capitalize">{trackingLabel(d)}</span>
              </div>
              {d.match_reason && (
                <button type="button" onClick={() => setMatchDetailsId(matchDetailsId === d.id ? null : d.id)} className="text-xs font-semibold text-brand-700 hover:text-brand-800">
                  {matchDetailsId === d.id ? 'Hide match details' : 'Why this match?'}
                </button>
              )}
              {d.delivery_id && d.volunteer_id && ['planned', 'en_route', 'picked_up', 'completed'].includes(d.delivery_status) && (
                <button type="button" onClick={() => setTrackingDonationId(d.id)} className="btn-primary min-h-10 px-3 py-2 text-sm">
                  <MapPin size={14} /> {trackingActionLabel(d)}
                </button>
              )}
            </div>
            {matchDetailsId === d.id && (
              <div className="mt-3 rounded-lg bg-gray-50 p-3 text-xs leading-5 text-gray-500">
                {d.match_reason}
                {d.match_probability != null && <p className="mt-1 font-medium text-brand-700">Confidence: {(d.match_probability * 100).toFixed(0)}%</p>}
              </div>
            )}

            {expandedId === d.id && (
              <div className="mt-5 border-t border-gray-100 pt-4 grid gap-4 text-sm text-gray-600 lg:grid-cols-2">
                <div className="space-y-2">
                  <p className="font-semibold text-gray-900">Donation details</p>
                  <p>Pickup: {d.pickup_address || `${d.pickup_lat.toFixed(5)}, ${d.pickup_lng.toFixed(5)}`}</p>
                  {d.degradation_hours != null && <p>Safe window: {d.degradation_hours} hours</p>}
                  <p>NGO: {relationshipLabel(d).ngo}</p>
                    <p>Volunteer: {relationshipLabel(d).volunteer}</p>
                    {requestSummary(d) && <p className="sm:col-span-2"><span className="font-medium text-gray-900">NGO requests:</span> {requestSummary(d)}</p>}
                </div>

                <div>
                  <p className="text-xs text-gray-500">Match details are available from the card action above.</p>
                  <p className="mt-4 font-semibold text-gray-900">Donation journey</p>
                  <div className="mt-2"><CompactJourney donation={d} /></div>
                </div>
              </div>
            )}
          </div>
        ))}
      </div>
      {trackingDonation && (
        <TrackVolunteerPanel
          donation={trackingDonation}
          livePosition={livePositions[trackingDonation.delivery_id]}
          connected={connected}
          onClose={() => setTrackingDonationId(null)}
        />
      )}
    </div>
  )
}
