import { useEffect, useRef, useState } from 'react'
import { api } from '../../api/client'
import { useAuth } from '../../context/AuthContext'
import { useToast } from '../../context/ToastContext'
import { PageHeader, ErrorBanner, DeliveryProgress, LoadingState, EmptyState } from '../../components/UI'
import MapView from '../../components/MapView'
import { useTrackingSocket } from '../../hooks/useTrackingSocket'
import { CheckCircle2, Star, Package, Truck, Warehouse, MapPin, HeartHandshake } from 'lucide-react'

function FeedbackForm({ donation, onDone }) {
  const [rating, setRating] = useState(5)
  const [comment, setComment] = useState('')
  const [submitting, setSubmitting] = useState(false)

  const submit = async () => {
    setSubmitting(true)
    try {
      await api.submitFeedback({
        donation_id: donation.id, target_type: 'donor', target_id: donation.donor_id,
        rating, comment_text: comment,
      })
      onDone()
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="mt-4 border-t border-gray-100 pt-4">
      <p className="mb-2 text-xs font-semibold uppercase tracking-[0.12em] text-gray-500">Rate donor quality</p>
      <div className="mb-2 flex gap-1">
        {[1, 2, 3, 4, 5].map((n) => (
          <button key={n} onClick={() => setRating(n)} type="button" aria-label={`Rate ${n} out of 5`}>
            <Star size={18} className={n <= rating ? 'fill-amber-400 text-amber-400' : 'text-gray-200'} />
          </button>
        ))}
      </div>
      <textarea className="input-field h-16 resize-none mb-2" placeholder="Optional comment…" value={comment} onChange={(e) => setComment(e.target.value)} />
      <button onClick={submit} disabled={submitting} className="text-xs btn-primary px-3 py-1.5">
        {submitting ? 'Submitting…' : 'Submit feedback'}
      </button>
    </div>
  )
}

export default function NgoDashboard() {
  const { user } = useAuth()
  const { notify } = useToast()
  const [donations, setDonations] = useState([])
  const [profile, setProfile] = useState(null)
  const [error, setError] = useState('')
  const [feedbackOpenFor, setFeedbackOpenFor] = useState(null)
  const [acceptingId, setAcceptingId] = useState(null)
  const [rejectingId, setRejectingId] = useState(null)
  const [livePositions, setLivePositions] = useState({})
  const [expandedId, setExpandedId] = useState(null)
  const [loading, setLoading] = useState(true)
  const connectionSeen = useRef(false)

  const selectedDonation = donations.find((donation) => donation.id === expandedId) || donations[0]

  const load = () => {
    api.ngoDonations().then((items) => {
      setDonations(items)
      setLivePositions((positions) => items.reduce((next, item) => {
        if (item.delivery_id && Number.isFinite(item.latest_location_lat) && Number.isFinite(item.latest_location_lng)) {
          next[item.delivery_id] = { lat: item.latest_location_lat, lng: item.latest_location_lng, delivery_id: item.delivery_id }
        }
        return next
      }, { ...positions }))
    }).catch((e) => setError(e.message)).finally(() => setLoading(false))
    api.ngoProfile().then(setProfile).catch(() => {})
  }
  const { lastMessage: liveMsg, connected } = useTrackingSocket(user ? `ngo:${user.id}` : null)

  useEffect(() => {
    load()
  }, [])

  useEffect(() => {
    if (connected) {
      load()
      if (connectionSeen.current) notify('Live tracking restored', { key: 'ngo:reconnected', tone: 'info' })
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
        donation_request: 'New donation request received',
        donation_available: 'New donation available',
        delivery_assigned: 'Volunteer assigned successfully',
        arrival_detected: 'Volunteer has arrived at the stop',
        stop_completed: 'Stop completed successfully',
        delivery_completed: 'Delivery completed successfully',
        route_deviation: 'Route deviation detected',
        route_recovered: 'Live route restored',
      }
      const message = messages[liveMsg.type]
      if (message) notify(message, { key: `ngo:${liveMsg.type}:${liveMsg.delivery_id || liveMsg.donation_id || liveMsg.timestamp}`, tone: liveMsg.type === 'route_deviation' ? 'warning' : 'success' })
    }
  }, [liveMsg])

  const confirmReceipt = async (id) => {
    setAcceptingId(id)
    setError('')
    try {
      await api.confirmReceipt(id)
      load()
    } catch (e) {
      setError(e.message)
    } finally {
      setAcceptingId(null)
    }
  }

  const rejectDonation = async (id) => {
    setRejectingId(id)
    setError('')
    try {
      await api.rejectDonation(id)
      notify('Donation declined; finding the next suitable NGO', { key: `ngo:rejected:${id}`, tone: 'info' })
      load()
    } catch (e) {
      setError(e.message)
    } finally {
      setRejectingId(null)
    }
  }

  const selectedLivePosition = selectedDonation?.delivery_id ? livePositions[selectedDonation.delivery_id] : null
  const selectedStops = selectedDonation?.delivery_stops?.length
    ? selectedDonation.delivery_stops
    : selectedDonation
      ? [{ lat: selectedDonation.pickup_lat, lng: selectedDonation.pickup_lng, stop_type: 'pickup', status: selectedDonation.status }]
      : []
  const markers = selectedDonation ? [
    ...selectedStops.map((stop, index) => ({
      id: `${selectedDonation.delivery_id || selectedDonation.id}-stop-${index}`,
      lat: stop.lat,
      lng: stop.lng,
      type: stop.stop_type === 'pickup' ? 'pickup' : index === selectedStops.length - 1 ? 'dropoff' : 'stop',
      glyph: String(index + 1),
      popup: stop.stop_type === 'pickup'
        ? `Food Pickup | ${selectedDonation.food_type} | ${selectedDonation.quantity_plates} plates | Status: ${selectedDonation.status}`
        : `NGO | ${profile?.name || selectedDonation.matched_ngo_name || 'Destination'} | Status: ${selectedDonation.delivery_status || selectedDonation.status}`,
    })),
    ...(selectedLivePosition ? [{
      id: `volunteer-${selectedDonation.delivery_id}`,
      live: true,
      lat: selectedLivePosition.lat,
      lng: selectedLivePosition.lng,
      type: 'volunteer',
      popup: `Volunteer | ${selectedDonation.volunteer_name || 'Assigned volunteer'} | Live GPS | Status: ${selectedDonation.delivery_status || selectedDonation.status}`,
    }] : []),
  ] : []

  const summary = {
    incoming: donations.filter((d) => d.status === 'matched').length,
    accepted: donations.filter((d) => ['ngo_accepted', 'assigned_volunteer', 'picked_up'].includes(d.status)).length,
    inTransit: donations.filter((d) => d.delivery_status === 'en_route').length,
    delivered: donations.filter((d) => d.status === 'delivered').length,
  }

  return (
    <div className="space-y-6 pb-8">
      <PageHeader title="Incoming Donations" subtitle="Review donation requests, accepted deliveries, and live delivery progress." />
      <ErrorBanner message={error} />

      {profile && (
        <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          <div className="rounded-2xl border border-gray-200 bg-white p-4 shadow-sm">
            <div className="flex items-center justify-between">
              <p className="text-xs font-semibold uppercase tracking-[0.12em] text-gray-500">Available capacity</p>
              <Warehouse size={16} className="text-brand-600" />
            </div>
            <p className="mt-3 text-3xl font-semibold text-gray-900">{profile.capacity_available}/{profile.capacity_total}</p>
          </div>
          <div className="rounded-2xl border border-gray-200 bg-white p-4 shadow-sm">
            <div className="flex items-center justify-between">
              <p className="text-xs font-semibold uppercase tracking-[0.12em] text-gray-500">Sentiment</p>
              <HeartHandshake size={16} className="text-emerald-600" />
            </div>
            <p className="mt-3 text-3xl font-semibold text-gray-900">{(profile.sentiment_score * 100).toFixed(0)}%</p>
          </div>
          <div className="rounded-2xl border border-gray-200 bg-white p-4 shadow-sm">
            <div className="flex items-center justify-between">
              <p className="text-xs font-semibold uppercase tracking-[0.12em] text-gray-500">Incoming requests</p>
              <Package size={16} className="text-blue-600" />
            </div>
            <p className="mt-3 text-3xl font-semibold text-gray-900">{summary.incoming}</p>
          </div>
          <div className="rounded-2xl border border-gray-200 bg-white p-4 shadow-sm">
            <div className="flex items-center justify-between">
              <p className="text-xs font-semibold uppercase tracking-[0.12em] text-gray-500">Accepted</p>
              <Truck size={16} className="text-amber-600" />
            </div>
            <p className="mt-3 text-3xl font-semibold text-gray-900">{summary.accepted}</p>
          </div>
          <div className="rounded-2xl border border-gray-200 bg-white p-4 shadow-sm">
            <div className="flex items-center justify-between">
              <p className="text-xs font-semibold uppercase tracking-[0.12em] text-gray-500">In transit</p>
              <Truck size={16} className="text-amber-600" />
            </div>
            <p className="mt-3 text-3xl font-semibold text-gray-900">{summary.inTransit}</p>
          </div>
          <div className="rounded-2xl border border-gray-200 bg-white p-4 shadow-sm">
            <div className="flex items-center justify-between">
              <p className="text-xs font-semibold uppercase tracking-[0.12em] text-gray-500">Cold storage</p>
              <Warehouse size={16} className="text-brand-600" />
            </div>
            <p className="mt-3 text-3xl font-semibold text-gray-900">{profile.has_cold_storage ? 'Yes' : 'No'}</p>
          </div>
          <div className="rounded-2xl border border-gray-200 bg-white p-4 shadow-sm">
            <div className="flex items-center justify-between">
              <p className="text-xs font-semibold uppercase tracking-[0.12em] text-gray-500">Delivered</p>
              <CheckCircle2 size={16} className="text-emerald-600" />
            </div>
            <p className="mt-3 text-3xl font-semibold text-emerald-700">{summary.delivered}</p>
          </div>
        </section>
      )}

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
        <div className="space-y-4">
          {loading && <LoadingState label="Loading donation requests..." />}
          {!loading && donations.length === 0 && <EmptyState title="No donation requests" message="New requests assigned to your NGO will appear here for review." icon={Package} />}
          {donations.map((d) => (
            <div key={d.id} className="rounded-3xl border border-gray-200 bg-white p-4 shadow-sm sm:p-5">
              <button type="button" onClick={() => setExpandedId(expandedId === d.id ? null : d.id)} className="w-full text-left">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="font-semibold text-gray-900 capitalize">{d.status === 'matched' ? 'New Donation Request · ' : ''}{d.food_type} · {d.quantity_plates} plates</p>
                    <p className="mt-1 flex items-center gap-1.5 text-xs text-gray-500"><MapPin size={12} /> {d.pickup_address}</p>
                  </div>
                  <span className="rounded-full bg-blue-100 px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.12em] text-blue-700">{d.status.replaceAll('_', ' ')}</span>
                </div>
              </button>

              <div className="mt-3">
                <DeliveryProgress status={d.status} deliveryStatus={d.delivery_status} />
              </div>

              {expandedId === d.id && (
                <div className="mt-4 border-t border-gray-100 pt-4 space-y-4 text-sm text-gray-600">
                  <div className="grid gap-2 sm:grid-cols-2">
                    <p>Donation: <span className="font-mono text-xs">{d.id}</span></p>
                    <p>Donor: {d.donor_name || 'Not available'}</p>
                    <p>Pickup: {d.pickup_address || `${d.pickup_lat.toFixed(5)}, ${d.pickup_lng.toFixed(5)}`}</p>
                    <p>Safe window: {d.degradation_hours != null ? `${d.degradation_hours} hours` : 'Not available'}</p>
                    <p>Match score: {d.match_probability != null ? `${(d.match_probability * 100).toFixed(0)}%` : 'Not available'}</p>
                    <p>Volunteer: {d.volunteer_name || 'Not assigned yet'}</p>
                    <p>Delivery: {d.delivery_id ? `#${d.delivery_id.slice(0, 8)}` : 'Not created yet'}</p>
                    <p>Delivery status: {d.delivery_status || 'Not started'}</p>
                  </div>
                  {d.match_reason && <p className="text-xs italic text-gray-500">“{d.match_reason}”</p>}
                  {d.delivery_stops?.length > 0 && (
                    <p>Current stop: {d.delivery_stops.find((stop) => stop.status !== 'completed')?.stop_type || 'Complete'} · Remaining: {d.delivery_stops.filter((stop) => stop.status !== 'completed').length}</p>
                  )}
                </div>
              )}

              {d.match_reason && <p className="mt-2 text-xs text-gray-500 italic">“{d.match_reason}”</p>}

              <div className="mt-4 flex flex-wrap items-center gap-3">
                {d.status === 'matched' && (
                  <button onClick={() => confirmReceipt(d.id)} disabled={acceptingId === d.id || rejectingId === d.id} className="btn-primary min-h-10 px-3 py-2 text-sm">
                    <CheckCircle2 size={15} /> {acceptingId === d.id ? 'Accepting…' : 'Accept donation'}
                  </button>
                )}
                {d.status === 'matched' && (
                  <button onClick={() => rejectDonation(d.id)} disabled={acceptingId === d.id || rejectingId === d.id} className="btn-secondary min-h-10 px-3 py-2 text-sm text-red-700 hover:border-red-200 hover:bg-red-50 hover:text-red-800">
                    {rejectingId === d.id ? 'Declining…' : 'Reject donation'}
                  </button>
                )}
                {d.status === 'delivered' && feedbackOpenFor !== d.id && (
                  <button onClick={() => setFeedbackOpenFor(d.id)} className="text-sm font-medium text-gray-600">
                    Leave feedback on donor →
                  </button>
                )}
              </div>

              {feedbackOpenFor === d.id && <FeedbackForm donation={d} onDone={() => { setFeedbackOpenFor(null); load() }} />}
            </div>
          ))}
        </div>

        <div className="rounded-3xl border border-gray-200 bg-white p-4 shadow-sm sm:p-5">
          <div className="mb-4 flex items-center justify-between">
            <div>
              <h2 className="text-xl font-semibold text-gray-900">Delivery map</h2>
              <p className="mt-1 text-xs text-gray-500">Showing the selected donation and its authorized delivery participants.</p>
            </div>
            <span className="rounded-full bg-brand-50 px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.12em] text-brand-700">Live view</span>
          </div>
          <div className="mb-3 flex flex-wrap gap-3 text-xs text-gray-600">
            <span className="flex items-center gap-1.5"><span className="h-2.5 w-2.5 rounded-full bg-amber-500" /> Food Pickup</span>
            <span className="flex items-center gap-1.5"><span className="h-2.5 w-2.5 rounded-full bg-brand-600" /> NGO / Destination</span>
            <span className="flex items-center gap-1.5"><span className="h-2.5 w-2.5 rounded-full bg-blue-600" /> Volunteer - Live GPS</span>
          </div>
          {selectedDonation ? (
            <>
              <div className="mb-3 flex flex-wrap items-center justify-between gap-2 rounded-xl bg-gray-50 px-3 py-2 text-sm">
                <span className="font-semibold capitalize text-gray-900">{selectedDonation.food_type} · {selectedDonation.quantity_plates} plates</span>
                <span className="capitalize text-gray-500">{selectedDonation.delivery_status || selectedDonation.status}</span>
              </div>
              <MapView
                markers={markers}
                route={selectedDonation.delivery_route}
                routeError={selectedDonation.delivery_route?.length > 1 ? null : 'Route temporarily unavailable'}
                fitPadding={56}
                maxFitZoom={15}
                height={520}
                zoom={13}
              />
              {selectedStops.length > 0 && (
                <div className="mt-4 rounded-xl border border-gray-200 bg-gray-50 p-4">
                  <p className="text-sm font-semibold text-gray-900">Delivery stops</p>
                  <div className="mt-3 grid gap-2 sm:grid-cols-2">
                    {selectedStops.map((stop, index) => (
                      <div key={`${stop.stop_type}-${index}`} className="flex items-start gap-3 rounded-lg border border-gray-200 bg-white p-3 text-sm">
                        <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-brand-50 font-semibold text-brand-800">{index + 1}</span>
                        <div className="min-w-0">
                          <p className="font-medium capitalize text-gray-900">{stop.stop_type === 'pickup' ? 'Pickup' : index === selectedStops.length - 1 ? 'Final drop-off' : 'Delivery stop'}</p>
                          <p className="mt-1 text-gray-500">{stop.status === 'completed' ? 'Completed' : stop.status || 'Pending'}</p>
                          {stop.estimated_arrival && <p className="mt-1 text-gray-500">ETA {new Date(stop.estimated_arrival).toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' })}</p>}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </>
          ) : (
            <div className="flex h-[320px] items-center justify-center rounded-xl border border-dashed border-gray-200 bg-gray-50 px-5 text-center text-sm text-gray-500">No donation is available to display yet.</div>
          )}
        </div>
      </div>
    </div>
  )
}
