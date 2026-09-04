import { createContext, useCallback, useContext, useEffect, useRef, useState } from 'react'
import { AlertTriangle, CheckCircle2, Info, X } from 'lucide-react'

const ToastContext = createContext(null)

const TONE_STYLES = {
  success: 'border-brand-200 bg-brand-50 text-brand-900',
  warning: 'border-amber-200 bg-amber-50 text-amber-900',
  info: 'border-gray-200 bg-white text-gray-900',
}

function ToastIcon({ tone }) {
  if (tone === 'warning') return <AlertTriangle size={17} className="text-amber-600" />
  if (tone === 'info') return <Info size={17} className="text-brand-600" />
  return <CheckCircle2 size={17} className="text-brand-600" />
}

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([])
  const timers = useRef(new Map())
  const recentKeys = useRef(new Set())
  const sequence = useRef(0)

  const dismiss = useCallback((id) => {
    setToasts((items) => items.filter((item) => item.id !== id))
    const timer = timers.current.get(id)
    if (timer) window.clearTimeout(timer)
    timers.current.delete(id)
  }, [])

  const notify = useCallback((message, options = {}) => {
    const key = options.key || message
    if (recentKeys.current.has(key)) return
    recentKeys.current.add(key)
    window.setTimeout(() => recentKeys.current.delete(key), options.dedupeMs || 10000)
    sequence.current += 1
    const id = `${Date.now()}-${sequence.current}`
    setToasts((items) => [...items.slice(-3), { id, message, tone: options.tone || 'success' }])
    timers.current.set(id, window.setTimeout(() => dismiss(id), options.duration || 4500))
  }, [dismiss])

  useEffect(() => () => {
    timers.current.forEach((timer) => window.clearTimeout(timer))
    timers.current.clear()
  }, [])

  return (
    <ToastContext.Provider value={{ notify, dismiss }}>
      {children}
      <div className="pointer-events-none fixed inset-x-4 top-4 z-[100] flex flex-col items-end gap-2 sm:left-auto sm:w-96" aria-live="polite" aria-atomic="true">
        {toasts.map((toast) => (
          <div key={toast.id} className={`pointer-events-auto flex w-full items-start gap-3 rounded-xl border px-4 py-3 text-sm shadow-lg ${TONE_STYLES[toast.tone] || TONE_STYLES.info}`} role="status">
            <ToastIcon tone={toast.tone} />
            <p className="min-w-0 flex-1 leading-5">{toast.message}</p>
            <button type="button" onClick={() => dismiss(toast.id)} className="rounded-md p-0.5 text-gray-400 hover:bg-black/5 hover:text-gray-700" aria-label="Dismiss notification" title="Dismiss notification">
              <X size={15} />
            </button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  )
}

export const useToast = () => useContext(ToastContext)
