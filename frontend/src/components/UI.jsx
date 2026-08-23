export function PageHeader({ title, subtitle }) {
  return (
    <div className="mb-6">
      <h1 className="text-2xl font-semibold text-gray-900">{title}</h1>
      {subtitle && <p className="text-gray-500 mt-1 text-sm">{subtitle}</p>}
    </div>
  )
}

export function StatBadge({ label, value, tone = 'default' }) {
  const tones = {
    default: 'bg-gray-100 text-gray-700',
    good: 'bg-brand-100 text-brand-800',
    bad: 'bg-red-100 text-red-700',
    warn: 'bg-amber-100 text-amber-800',
  }
  return (
    <div className={`rounded-xl px-4 py-3 ${tones[tone]}`}>
      <p className="text-[11px] uppercase tracking-wide opacity-70">{label}</p>
      <p className="text-xl font-semibold mt-0.5">{value}</p>
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
      <div className="flex justify-between text-xs text-gray-500 mb-1">
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
    <div className="bg-red-50 border border-red-100 text-red-700 text-sm rounded-xl px-4 py-3 mb-4">
      {message}
    </div>
  )
}
