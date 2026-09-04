export function PageHeader({ title, subtitle }) {
  return (
    <div className="mb-6 rounded-2xl border border-gray-200/90 bg-white p-5 shadow-sm sm:p-6">
      <div className="flex flex-col gap-2 md:flex-row md:items-end md:justify-between">
        <div>
          <p className="eyebrow">Operations</p>
          <h1 className="mt-1 text-2xl font-semibold tracking-tight text-gray-900 sm:text-3xl">{title}</h1>
        </div>
      </div>
      {subtitle && <p className="mt-2 max-w-2xl text-sm leading-6 text-gray-600">{subtitle}</p>}
    </div>
  )
}

export function StatBadge({ label, value, tone = 'default' }) {
  const tones = {
    default: 'border-gray-200 bg-gray-50 text-gray-800',
    good: 'border-brand-200 bg-brand-50 text-brand-800',
    bad: 'border-red-200 bg-red-50 text-red-700',
    warn: 'border-amber-200 bg-amber-50 text-amber-800',
  }
  return (
    <div className={`rounded-xl border p-4 shadow-sm ${tones[tone]}`}>
      <p className="text-xs font-bold uppercase tracking-[0.12em] text-gray-500">{label}</p>
      <p className="mt-2 text-2xl font-semibold tracking-tight sm:text-3xl">{value}</p>
    </div>
  )
}

export function ProbabilityBar({ label, value, tone = 'brand' }) {
  const colors = {
    brand: 'bg-brand-500',
    red: 'bg-red-500',
    amber: 'bg-amber-500',
    gray: 'bg-gray-400',
  }
  const pct = Math.round(value * 100)
  return (
    <div className="mb-2">
      <div className="mb-1 flex justify-between text-sm text-gray-500">
        <span>{label}</span>
        <span>{pct}%</span>
      </div>
      <div className="w-full h-2 bg-gray-100 rounded-full overflow-hidden">
        <div className={`h-full ${colors[tone]} rounded-full transition-all`} style={{ width: `${pct}%` }} />
      </div>
    </div>
  )
}

export function ErrorBanner({ message }) {
  if (!message) return null
  return (
    <div className="mb-4 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm leading-6 text-red-700" role="alert">
      {message}
    </div>
  )
}

export function LoadingState({ label = 'Loading...' }) {
  return <div className="flex items-center gap-3 rounded-2xl border border-gray-200 bg-white px-5 py-8 text-sm text-gray-600 shadow-sm" role="status"><span className="h-4 w-4 animate-spin rounded-full border-2 border-gray-200 border-t-brand-600" aria-hidden="true" />{label}</div>
}

export function EmptyState({ title, message, icon: Icon }) {
  return <div className="flex flex-col items-center justify-center rounded-2xl border border-dashed border-gray-200 bg-gray-50 px-6 py-12 text-center">{Icon && <Icon size={28} className="mb-3 text-gray-300" />}<p className="font-semibold text-gray-800">{title}</p>{message && <p className="mt-2 max-w-md text-sm leading-6 text-gray-500">{message}</p>}</div>
}

const DELIVERY_STEPS = [
  ['submitted', 'Submitted'],
  ['matched', 'NGO Accepted'],
  ['assigned_volunteer', 'Volunteer Assigned'],
  ['picked_up', 'Picked Up'],
  ['en_route', 'In Transit'],
  ['delivered', 'Delivered'],
]

export function DeliveryProgress({ status, deliveryStatus }) {
  const effectiveStatus = deliveryStatus === 'completed'
    ? 'delivered'
    : deliveryStatus === 'en_route' && status === 'picked_up'
      ? 'en_route'
      : status === 'ngo_accepted'
        ? 'matched'
      : status === 'matched'
        ? 'submitted'
        : status
  const index = Math.max(0, DELIVERY_STEPS.findIndex(([key]) => key === effectiveStatus))

  return (
    <div className="mt-3 flex flex-wrap items-center gap-1.5">
      {DELIVERY_STEPS.map(([key, label], step) => (
        <div key={key} className={`whitespace-nowrap rounded-full px-2.5 py-1.5 text-xs ${step === index ? 'bg-brand-100 font-semibold text-brand-800' : step < index ? 'bg-gray-100 text-gray-600' : 'bg-gray-50 text-gray-400'}`}>
          {label}
        </div>
      ))}
    </div>
  )
}

const JOURNEY_STEPS = [
  ['created', 'Donation Created'],
  ['matched', 'NGO Matched'],
  ['accepted', 'NGO Accepted'],
  ['assigned_volunteer', 'Volunteer Assigned'],
  ['started', 'Volunteer Started'],
  ['picked_up', 'Food Picked Up'],
  ['en_route', 'In Transit'],
  ['delivered', 'Delivered'],
]

export function JourneyTimeline({ status, deliveryStatus }) {
  const current = deliveryStatus === 'completed' || status === 'delivered'
    ? 'delivered'
    : deliveryStatus === 'en_route'
      ? 'en_route'
      : status === 'picked_up'
        ? 'picked_up'
        : status === 'assigned_volunteer'
          ? 'assigned_volunteer'
          : status === 'matched'
            ? 'matched'
            : 'created'
  const currentIndex = JOURNEY_STEPS.findIndex(([key]) => key === current)

  return (
    <div className="space-y-1.5 mt-3">
      {JOURNEY_STEPS.map(([key, label], index) => (
        <div key={key} className={`flex items-center gap-2 text-sm ${index === currentIndex ? 'font-semibold text-brand-800' : index < currentIndex ? 'text-gray-600' : 'text-gray-400'}`}>
          <span className={`flex h-5 w-5 items-center justify-center rounded-full text-xs ${index <= currentIndex ? 'bg-brand-100 text-brand-700' : 'bg-gray-100 text-gray-400'}`}>
            {index < currentIndex ? '✓' : index + 1}
          </span>
          <span>{label}</span>
        </div>
      ))}
    </div>
  )
}
