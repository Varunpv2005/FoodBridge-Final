import { useEffect, useState } from 'react'
import { api } from '../../api/client'
import { PageHeader, ErrorBanner, StatBadge, LoadingState } from '../../components/UI'
import { ResponsiveContainer, LineChart, Line, XAxis, YAxis, Tooltip, Legend, CartesianGrid } from 'recharts'

export default function AdminOverview() {
  const [overview, setOverview] = useState(null)
  const [error, setError] = useState('')
  const [forecast, setForecast] = useState(null)
  const [forecastError, setForecastError] = useState('')

  useEffect(() => {
    const load = () => api.overview().then(setOverview).catch((e) => setError(e.message))
    load()
    const t = setInterval(load, 8000)
    return () => clearInterval(t)
  }, [])

  useEffect(() => {
    api.demandForecast(7).then(setForecast).catch((e) => setForecastError(e.message))
  }, [])

  return (
    <div className="space-y-6 pb-8">
      <PageHeader title="Platform Overview" subtitle="Live totals across donors, NGOs, volunteers, and the ML decision pipeline." />
      <ErrorBanner message={error} />
      {!overview && !error && <LoadingState label="Loading platform overview..." />}

      {overview && (
        <>
          <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <StatBadge label="Total donations" value={overview.totals.donations} />
            <StatBadge label="Total deliveries" value={overview.totals.deliveries} />
            <StatBadge label="Active (en route)" value={overview.active_deliveries} tone="good" />
            <StatBadge label="Anomalies pending" value={overview.anomalies_pending} tone={overview.anomalies_pending > 0 ? 'bad' : 'default'} />
          </section>

          <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <StatBadge label="Donors" value={overview.totals.donors} />
            <StatBadge label="NGOs" value={overview.totals.ngos} />
            <StatBadge label="Volunteers" value={overview.totals.volunteers} />
            <StatBadge label="Plates delivered" value={overview.total_plates_delivered} tone="good" />
          </section>

          <div className="grid gap-6 xl:grid-cols-[1.1fr_1.4fr]">
            <div className="rounded-3xl border border-gray-200 bg-white p-5 shadow-sm">
              <h3 className="text-xl font-semibold text-gray-900">Donations by status</h3>
              <div className="mt-4 space-y-3">
                {Object.entries(overview.donations_by_status).map(([status, count]) => (
                  <div key={status} className="rounded-2xl border border-gray-100 bg-gray-50 px-3 py-2">
                    <div className="flex items-center justify-between text-sm">
                      <span className="text-gray-600 capitalize">{status.replaceAll('_', ' ')}</span>
                      <span className="font-semibold text-gray-900">{count}</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            <div className="rounded-3xl border border-gray-200 bg-white p-5 shadow-sm">
              <div className="mb-4 flex items-start justify-between gap-4">
                <div>
                  <h3 className="text-xl font-semibold text-gray-900">AI demand forecast</h3>
                  {forecast && <p className="mt-1 text-xs text-gray-500">{forecast.region} · {forecast.food_type}</p>}
                </div>
                {forecast && <span className="rounded-full bg-brand-50 px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.12em] text-brand-700">Next {forecast.forecasts.length} days</span>}
              </div>
              {forecastError && <p className="text-sm text-red-700">{forecastError}</p>}
              {forecast && (
                <>
                  <div className="h-72">
                    <ResponsiveContainer width="100%" height="100%">
                      <LineChart data={forecast.forecasts} margin={{ top: 8, right: 12, left: 0, bottom: 8 }}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                        <XAxis dataKey="forecast_date" tick={{ fontSize: 11 }} />
                        <YAxis tick={{ fontSize: 11 }} />
                        <Tooltip />
                        <Legend />
                        <Line type="monotone" dataKey="predicted_demand" name="Ensemble" stroke="#2563eb" strokeWidth={3} dot={false} />
                        <Line type="monotone" dataKey="xgboost_prediction" name="XGBoost" stroke="#16a34a" strokeWidth={1.5} dot={false} />
                        <Line type="monotone" dataKey="lstm_prediction" name="LSTM" stroke="#ea580c" strokeWidth={1.5} dot={false} />
                      </LineChart>
                    </ResponsiveContainer>
                  </div>
                  <div className="mt-4 grid grid-cols-2 gap-3 text-xs text-gray-600 md:grid-cols-4">
                    <div className="rounded-xl bg-gray-50 p-2.5">Ensemble weight: <span className="font-medium text-gray-900">{forecast.model_weights.xgboost} XGB / {forecast.model_weights.lstm} LSTM</span></div>
                    <div className="rounded-xl bg-gray-50 p-2.5">Test MAE: <span className="font-medium text-gray-900">{forecast.metrics.ensemble.mae}</span></div>
                    <div className="rounded-xl bg-gray-50 p-2.5">Test RMSE: <span className="font-medium text-gray-900">{forecast.metrics.ensemble.rmse}</span></div>
                    <div className="rounded-xl bg-gray-50 p-2.5">Sequence: <span className="font-medium text-gray-900">{forecast.sequence_length} days</span></div>
                  </div>
                </>
              )}
            </div>
          </div>
        </>
      )}
    </div>
  )
}
