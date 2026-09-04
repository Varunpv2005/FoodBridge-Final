import { useEffect, useState } from 'react'
import { BarChart3, ClipboardCheck, Database, FlaskConical, Info, TrendingDown, TrendingUp } from 'lucide-react'
import { api } from '../../api/client'
import { PAPER_EVALUATION, displayMetric, improvement } from '../../data/paperEvaluation'
import { EmptyState, ErrorBanner, LoadingState, PageHeader } from '../../components/UI'

function ResultCard({ metric, value, before, change, icon: Icon }) {
  const positive = metric.direction === 'higher' ? <TrendingUp size={16} /> : <TrendingDown size={16} />
  return (
    <div className="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <p className="text-sm font-semibold text-gray-700">{metric.label}</p>
        <Icon size={18} className="text-brand-700" aria-hidden="true" />
      </div>
      <p className="mt-4 text-3xl font-semibold tracking-tight text-gray-950">{value}</p>
      <p className="mt-2 text-sm text-gray-500">Before: {before}</p>
      <p className="mt-2 inline-flex items-center gap-1.5 text-sm font-semibold text-brand-700">{positive} {change}</p>
    </div>
  )
}

function ComparisonBars({ metric }) {
  const scale = Math.max(metric.before, metric.after)
  return (
    <div className="border-b border-gray-100 py-4 last:border-0">
      <div className="flex items-center justify-between gap-3 text-sm">
        <span className="font-medium text-gray-800">{metric.label}</span>
        <span className="text-gray-500">{metric.direction === 'higher' ? 'Higher is better' : 'Lower is better'}</span>
      </div>
      <div className="mt-3 grid grid-cols-[5.5rem_minmax(0,1fr)_4.5rem] items-center gap-3 text-sm">
        <span className="text-gray-500">Before</span>
        <div className="h-3 overflow-hidden rounded-full bg-gray-100"><div className="h-full rounded-full bg-gray-400" style={{ width: `${(metric.before / scale) * 100}%` }} /></div>
        <span className="text-right font-medium text-gray-700">{displayMetric(metric.before, metric.unit)}</span>
      </div>
      <div className="mt-2 grid grid-cols-[5.5rem_minmax(0,1fr)_4.5rem] items-center gap-3 text-sm">
        <span className="font-medium text-brand-800">FoodBridge</span>
        <div className="h-3 overflow-hidden rounded-full bg-brand-50"><div className="h-full rounded-full bg-brand-600" style={{ width: `${(metric.after / scale) * 100}%` }} /></div>
        <span className="text-right font-semibold text-brand-800">{displayMetric(metric.after, metric.unit)}</span>
      </div>
    </div>
  )
}

function ComparisonTable() {
  return (
    <div className="overflow-x-auto rounded-xl border border-gray-200">
      <table className="w-full min-w-[680px] text-left text-sm">
        <thead className="bg-gray-50 text-gray-600"><tr><th className="px-4 py-3 font-semibold">Metric</th><th className="px-4 py-3 font-semibold">Manual</th><th className="px-4 py-3 font-semibold">Rule-Based</th><th className="px-4 py-3 font-semibold text-brand-800">FoodBridge</th></tr></thead>
        <tbody>{PAPER_EVALUATION.comparison.map((row) => <tr key={row.label} className="border-t border-gray-100"><td className="px-4 py-3 font-medium text-gray-800">{row.label}</td><td className="px-4 py-3 text-gray-600">{displayMetric(row.manual, row.unit)}</td><td className="px-4 py-3 text-gray-600">{displayMetric(row.ruleBased, row.unit)}</td><td className="px-4 py-3 font-semibold text-brand-800">{displayMetric(row.foodbridge, row.unit)}</td></tr>)}</tbody>
      </table>
    </div>
  )
}

export default function EvaluationResults() {
  const [operationalCount, setOperationalCount] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    api.evaluationResults().then((data) => setOperationalCount(data.operational_data?.record_count ?? 0)).catch((requestError) => setError(requestError.message))
  }, [])

  const cards = [
    [PAPER_EVALUATION.optimization[0], '91.7%', '58.3%', 'matching'],
    [PAPER_EVALUATION.optimization[1], '42 min', '78 min', 'delivery'],
    [PAPER_EVALUATION.optimization[2], '0.28', '0.72', 'risk'],
    [PAPER_EVALUATION.optimization[3], '82%', '45%', 'utilization'],
    [PAPER_EVALUATION.optimization[4], '7.2%', '18.4%', 'forecast'],
  ]
  const cardIcons = { matching: ClipboardCheck, delivery: TrendingDown, risk: FlaskConical, utilization: TrendingUp, forecast: BarChart3 }
  const spoilageMetric = { label: 'Spoilage Incidents', direction: 'lower', before: 23.5, after: 6.8 }

  return (
    <div className="space-y-6 pb-8">
      <PageHeader title="Results & Evaluation" subtitle="FoodBridge Evaluation Results — Simulation / Pilot-Oriented Setup" />
      <ErrorBanner message={error} />
      <div className="flex items-start gap-3 rounded-2xl border border-brand-200 bg-brand-50 p-4 text-sm text-brand-900"><Info size={18} className="mt-0.5 shrink-0" /><p>Results reported in the FoodBridge evaluation under the stated experimental setup. These are not live production statistics.</p></div>

      <section>
        <div className="mb-4 flex items-end justify-between gap-3"><div><p className="eyebrow">Table I</p><h2 className="mt-1 text-xl font-semibold text-gray-900">FoodBridge Optimization Results</h2></div><p className="text-sm text-gray-500">Before vs FoodBridge</p></div>
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">{cards.map(([metric, value, before, key]) => <ResultCard key={key} metric={metric} value={value} before={before} change={improvement(metric)} icon={cardIcons[key]} />)}<ResultCard metric={spoilageMetric} value="6.8%" before="23.5% manual" change={`${(((23.5 - 6.8) / 23.5) * 100).toFixed(1)}% reduction versus manual coordination`} icon={TrendingDown} /></div>
      </section>

      <section className="card"><div className="mb-4 flex items-start justify-between gap-3"><div><p className="eyebrow">Figure 1</p><h2 className="mt-1 text-xl font-semibold text-gray-900">Before vs FoodBridge</h2></div><p className="text-sm text-gray-500">Bars are scaled within each metric</p></div>{PAPER_EVALUATION.optimization.map((metric) => <ComparisonBars key={metric.key} metric={metric} />)}</section>

      <section className="card"><p className="eyebrow">Table II</p><h2 className="mt-1 text-xl font-semibold text-gray-900">Comparison with Existing Coordination Approaches</h2><p className="mt-1 text-sm text-gray-600">Reported comparative values from the paper evaluation.</p><div className="mt-4"><ComparisonTable /></div></section>

      <section className="card"><div className="flex items-center gap-3"><TrendingUp size={19} className="text-brand-700" /><h2 className="text-xl font-semibold text-gray-900">Key Findings</h2></div><ul className="mt-4 space-y-3 text-sm leading-6 text-gray-700"><li>FoodBridge improves matching accuracy from 58.3% to 91.7%.</li><li>Average delivery time decreases from 78 minutes to 42 minutes.</li><li>Estimated spoilage-risk exposure decreases from 0.72 to 0.28.</li><li>Volunteer utilization increases from 45% to 82%.</li><li>Demand forecasting RMSE decreases from 18.4% to 7.2%.</li><li>Reported spoilage incidents decrease to 6.8% compared with 23.5% for manual coordination.</li></ul></section>

      <section className="card"><div className="flex items-center gap-3"><Database size={19} className="text-gray-600" /><h2 className="text-xl font-semibold text-gray-900">Current Operational Data</h2></div>{operationalCount == null ? <p className="mt-3 text-sm text-gray-500">Loading operational record count...</p> : <p className="mt-3 text-sm text-gray-700"><span className="text-2xl font-semibold text-gray-900">{operationalCount}</span> operational records. These records are separate from the paper evaluation and are not used in its reported results.</p>}</section>

      <section className="card"><div className="flex items-center gap-3"><ClipboardCheck size={19} className="text-brand-700" /><h2 className="text-xl font-semibold text-gray-900">Evaluation Context</h2></div><ul className="mt-4 grid gap-2 text-sm leading-6 text-gray-700 sm:grid-cols-2">{PAPER_EVALUATION.context.map((item) => <li key={item}>• {item}</li>)}</ul></section>

      <p className="rounded-xl border border-gray-200 bg-gray-50 px-4 py-3 text-sm leading-6 text-gray-600"><strong className="text-gray-800">Interpretation:</strong> These results are reported for the stated simulation/pilot-oriented evaluation setup. They indicate relative improvement under the evaluated conditions and should not be interpreted as universal guarantees across cities, seasons, food categories, or deployment conditions.</p>
    </div>
  )
}
