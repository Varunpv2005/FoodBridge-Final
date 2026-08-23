import { useEffect, useState } from 'react'
import { api } from '../../api/client'
import { PageHeader, ErrorBanner } from '../../components/UI'
import { ShieldAlert, Check, X } from 'lucide-react'

export default function AnomalyQueue() {
  const [items, setItems] = useState([])
  const [error, setError] = useState('')

  const load = () => api.anomalyQueue().then(setItems).catch((e) => setError(e.message))

  useEffect(() => {
    load()
    const t = setInterval(load, 8000)
    return () => clearInterval(t)
  }, [])

  const approve = async (id) => { await api.approveAnomaly(id); load() }
  const reject = async (id) => { await api.rejectAnomaly(id); load() }

  return (
    <div>
      <PageHeader title="Anomaly Review Queue" subtitle="Donations flagged by the Isolation Forest + SHAP-explained Random Forest as unusual donor behavior." />
      <ErrorBanner message={error} />

      {items.length === 0 && (
        <div className="card text-center text-gray-400 py-12 flex flex-col items-center gap-2">
          <ShieldAlert size={24} className="text-gray-300" />
          No anomalies pending review.
        </div>
      )}

      <div className="space-y-4">
        {items.map((d) => (
          <div key={d.id} className="card border-l-4 border-l-red-400">
            <div className="flex items-center justify-between mb-2">
              <p className="font-medium text-gray-900 capitalize">{d.food_type} · {d.quantity_plates} plates</p>
              <span className="text-xs px-2 py-1 rounded-full bg-red-100 text-red-700">
                {(d.anomaly_probability * 100).toFixed(1)}% anomaly probability
              </span>
            </div>
            <p className="text-xs text-gray-400 mb-3">{d.pickup_address}</p>

            {d.anomaly_shap && (
              <div className="mb-4">
                <p className="text-xs font-semibold text-gray-500 uppercase mb-2">SHAP: why this was flagged</p>
                <div className="space-y-1.5">
                  {Object.entries(d.anomaly_shap).map(([feat, val]) => (
                    <div key={feat} className="flex items-center gap-2">
                      <span className="text-xs text-gray-500 w-44 truncate">{feat}</span>
                      <div className="flex-1 h-2 bg-gray-100 rounded-full overflow-hidden">
                        <div className={`h-full ${val >= 0 ? 'bg-red-400' : 'bg-gray-300'}`} style={{ width: `${Math.min(Math.abs(val) * 300, 100)}%` }} />
                      </div>
                      <span className="text-xs text-gray-400 w-14 text-right">{val > 0 ? '+' : ''}{val}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            <div className="flex gap-2">
              <button onClick={() => approve(d.id)} className="flex items-center gap-1 text-xs px-3 py-1.5 rounded-lg bg-brand-600 text-white font-medium">
                <Check size={14} /> Approve & re-run matching
              </button>
              <button onClick={() => reject(d.id)} className="flex items-center gap-1 text-xs px-3 py-1.5 rounded-lg bg-red-50 text-red-600 font-medium">
                <X size={14} /> Reject donation
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
