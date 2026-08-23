import { useState } from 'react'
import { api } from '../../api/client'
import { PageHeader, ErrorBanner, ProbabilityBar } from '../../components/UI'
import { Camera, MessageSquareText } from 'lucide-react'

function ImageTab() {
  const [file, setFile] = useState(null)
  const [preview, setPreview] = useState(null)
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')

  const onFile = (f) => { if (!f) return; setFile(f); setPreview(URL.createObjectURL(f)) }
  const run = async () => {
    setError('')
    try { setResult(await api.mlImageQuality(file)) } catch (e) { setError(e.message) }
  }

  return (
    <div className="grid grid-cols-2 gap-4">
      <div>
        <label className="border-2 border-dashed border-gray-200 rounded-xl h-40 flex items-center justify-center cursor-pointer overflow-hidden block">
          {preview ? <img src={preview} className="h-full w-full object-cover" /> : <Camera className="text-gray-300" />}
          <input type="file" accept="image/*" className="hidden" onChange={(e) => onFile(e.target.files[0])} />
        </label>
        <button className="btn-primary w-full mt-3" onClick={run} disabled={!file}>Check quality</button>
      </div>
      <div>
        <ErrorBanner message={error} />
        {result && (
          <div className={`rounded-xl p-4 ${result.label.includes('Safe') ? 'bg-brand-50' : 'bg-red-50'}`}>
            <p className="font-semibold">{result.label}</p>
            <p className="text-xs text-gray-500">{(result.confidence * 100).toFixed(1)}% confidence</p>
          </div>
        )}
      </div>
    </div>
  )
}

function SentimentTab() {
  const [text, setText] = useState('Prompt delivery, food was fresh and well-packed.')
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')
  const run = async () => {
    setError('')
    try { setResult(await api.mlSentiment(text)) } catch (e) { setError(e.message) }
  }
  return (
    <div>
      <textarea className="input-field h-24 mb-3" value={text} onChange={(e) => setText(e.target.value)} />
      <button className="btn-primary" onClick={run}>Analyze</button>
      <ErrorBanner message={error} />
      {result && (
        <div className="mt-4">
          {Object.entries(result.probabilities).map(([l, p]) => <ProbabilityBar key={l} label={l} value={p} />)}
        </div>
      )}
    </div>
  )
}

const TABS = [
  { id: 'image', label: 'Image Quality (CNN)', icon: Camera, Comp: ImageTab },
  { id: 'sentiment', label: 'Sentiment (NLP)', icon: MessageSquareText, Comp: SentimentTab },
]

export default function MlPlayground() {
  const [active, setActive] = useState('image')
  const Active = TABS.find((t) => t.id === active).Comp

  return (
    <div>
      <PageHeader title="ML Playground" subtitle="Test each model standalone, outside the live donation pipeline." />
      <div className="flex gap-2 mb-6">
        {TABS.map((t) => (
          <button key={t.id} onClick={() => setActive(t.id)}
                  className={`text-sm px-4 py-2 rounded-lg font-medium ${active === t.id ? 'bg-brand-600 text-white' : 'bg-gray-100 text-gray-600'}`}>
            {t.label}
          </button>
        ))}
      </div>
      <div className="card"><Active /></div>
    </div>
  )
}
