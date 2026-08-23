import { useEffect, useState } from 'react'
import { api } from '../../api/client'
import { PageHeader, ErrorBanner } from '../../components/UI'
import MapView from '../../components/MapView'
import { CheckCircle2, Star } from 'lucide-react'

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
    <div className="mt-3 border-t border-gray-100 pt-3">
      <p className="text-xs font-medium text-gray-500 mb-2">Rate this donor's food quality</p>
      <div className="flex gap-1 mb-2">
        {[1, 2, 3, 4, 5].map((n) => (
          <button key={n} onClick={() => setRating(n)}>
            <Star size={18} className={n <= rating ? 'fill-amber-400 text-amber-400' : 'text-gray-200'} />
          </button>
        ))}
      </div>
      <textarea className="input-field h-16 resize-none mb-2" placeholder="Optional comment…"
                value={comment} onChange={(e) => setComment(e.target.value)} />
      <button onClick={submit} disabled={submitting} className="text-xs btn-primary px-3 py-1.5">
        {submitting ? 'Submitting…' : 'Submit feedback'}
      </button>
    </div>
  )
}

export default function NgoDashboard() {
  const [donations, setDonations] = useState([])
  const [profile, setProfile] = useState(null)
  const [error, setError] = useState('')
  const [feedbackOpenFor, setFeedbackOpenFor] = useState(null)

  const load = () => {
    api.ngoDonations().then(setDonations).catch((e) => setError(e.message))
    api.ngoProfile().then(setProfile).catch(() => {})
  }

  useEffect(() => {
    load()
    const t = setInterval(load, 8000)
    return () => clearInterval(t)
  }, [])

  const confirmReceipt = async (id) => {
    await api.confirmReceipt(id)
    load()
  }

  const markers = profile ? [{ lat: profile.lat, lng: profile.lng, type: 'ngo', popup: profile.name }] : []
  donations.forEach((d) => markers.push({ lat: d.pickup_lat, lng: d.pickup_lng, type: 'donor', popup: `${d.food_type} · ${d.quantity_plates} plates` }))

  return (
    <div>
      <PageHeader title="Incoming Donations" subtitle="Donations matched to your NGO by the assignment engine." />
      <ErrorBanner message={error} />

      {profile && (
        <div className="grid grid-cols-3 gap-3 mb-6">
          <div className="card"><p className="text-xs text-gray-400">Capacity available</p><p className="text-xl font-semibold">{profile.capacity_available}/{profile.capacity_total}</p></div>
          <div className="card"><p className="text-xs text-gray-400">Sentiment score</p><p className="text-xl font-semibold">{(profile.sentiment_score * 100).toFixed(0)}%</p></div>
          <div className="card"><p className="text-xs text-gray-400">Cold storage</p><p className="text-xl font-semibold">{profile.has_cold_storage ? 'Yes' : 'No'}</p></div>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="space-y-3">
          {donations.length === 0 && <div className="card text-center text-gray-400 py-12">No donations matched yet.</div>}
          {donations.map((d) => (
            <div key={d.id} className="card">
              <div className="flex items-center justify-between">
                <p className="font-medium text-gray-900 capitalize">{d.food_type} · {d.quantity_plates} plates</p>
                <span className="text-xs px-2 py-1 rounded-full bg-blue-100 text-blue-700">{d.status.replaceAll('_', ' ')}</span>
              </div>
              <p className="text-xs text-gray-400 mt-1">{d.pickup_address}</p>
              {d.match_reason && <p className="text-xs text-gray-500 mt-1 italic">"{d.match_reason}"</p>}
              {d.status === 'assigned_volunteer' && (
                <button onClick={() => confirmReceipt(d.id)} className="mt-3 text-xs flex items-center gap-1 text-brand-700 font-medium">
                  <CheckCircle2 size={14} /> Confirm receipt
                </button>
              )}
              {d.status === 'delivered' && feedbackOpenFor !== d.id && (
                <button onClick={() => setFeedbackOpenFor(d.id)} className="mt-3 text-xs text-gray-500 font-medium">
                  Leave feedback on donor →
                </button>
              )}
              {feedbackOpenFor === d.id && <FeedbackForm donation={d} onDone={() => { setFeedbackOpenFor(null); load() }} />}
            </div>
          ))}
        </div>
        <MapView markers={markers} height={480} />
      </div>
    </div>
  )
}
