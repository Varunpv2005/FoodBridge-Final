import { useEffect, useRef, useState } from 'react'
import { api } from '../api/client'
import { useAuth } from '../context/AuthContext'
import { MessageCircle, Mic, Send, Volume2, X } from 'lucide-react'

const LANGUAGES = [
  { value: 'en', label: 'English', speech: 'en-US' },
  { value: 'hi', label: 'Hindi', speech: 'hi-IN' },
  { value: 'kn', label: 'Kannada', speech: 'kn-IN' },
]

function renderInlineMarkdown(text, keyPrefix) {
  return text.split(/(\*\*[^*]+\*\*|`[^`]+`|\*[^*]+\*)/g).map((part, index) => {
    const key = `${keyPrefix}-${index}`
    if (part.startsWith('**') && part.endsWith('**')) {
      return <strong key={key}>{part.slice(2, -2)}</strong>
    }
    if (part.startsWith('`') && part.endsWith('`')) {
      return <code key={key}>{part.slice(1, -1)}</code>
    }
    if (part.startsWith('*') && part.endsWith('*')) {
      return <em key={key}>{part.slice(1, -1)}</em>
    }
    return part
  })
}

function renderAssistantMarkdown(text) {
  const lines = text.split(/\r?\n/)
  const content = []
  let listItems = []
  let listType = null

  const flushList = () => {
    if (!listItems.length) return
    const List = listType === 'ordered' ? 'ol' : 'ul'
    content.push(<List key={`list-${content.length}`} className="my-2 space-y-1 pl-5">
      {listItems.map((item, index) => <li key={`item-${index}`}>{renderInlineMarkdown(item, `item-${index}`)}</li>)}
    </List>)
    listItems = []
    listType = null
  }

  lines.forEach((line, index) => {
    const trimmed = line.trim()
    const unordered = trimmed.match(/^[-*]\s+(.+)/)
    const ordered = trimmed.match(/^\d+[.)]\s+(.+)/)
    if (unordered || ordered) {
      const nextType = ordered ? 'ordered' : 'unordered'
      if (listType && listType !== nextType) flushList()
      listType = nextType
      listItems.push((ordered || unordered)[1])
      return
    }
    flushList()
    if (!trimmed) return
    const heading = trimmed.match(/^#{1,3}\s+(.+)/)
    if (heading) {
      content.push(<p key={`heading-${index}`} className="mt-3 font-semibold text-gray-900 first:mt-0">{renderInlineMarkdown(heading[1], `heading-${index}`)}</p>)
      return
    }
    content.push(<p key={`paragraph-${index}`} className="my-2 first:mt-0 last:mb-0">{renderInlineMarkdown(trimmed, `paragraph-${index}`)}</p>)
  })
  flushList()
  return content
}

function containsKannada(text) {
  return /[\u0C80-\u0CFF]/.test(text)
}

function containsHindi(text) {
  return /[\u0900-\u097F]/.test(text)
}

function cleanSpeechText(text) {
  return text
    .replace(/```[\s\S]*?```/g, ' ')
    .replace(/`([^`]+)`/g, '$1')
    .replace(/\*\*([^*]+)\*\*/g, '$1')
    .replace(/\*([^*]+)\*/g, '$1')
    .replace(/^#{1,3}\s+/gm, '')
    .replace(/^\s*[-*]\s+/gm, '')
    .replace(/^\s*\d+[.)]\s+/gm, '')
    .replace(/\s+/g, ' ')
    .trim()
}

function speechLanguage(text) {
  if (containsKannada(text)) return 'kn-IN'
  if (containsHindi(text)) return 'hi-IN'
  return 'en-IN'
}

function matchingVoice(voices, languageCode) {
  const normalized = languageCode.toLowerCase()
  const family = normalized.split('-')[0]
  return voices.find((voice) => voice.lang.toLowerCase() === normalized)
    || voices.find((voice) => voice.lang.toLowerCase().startsWith(`${family}-`))
}

export default function AssistantPanel() {
  const { user } = useAuth()
  const [open, setOpen] = useState(false)
  const [language, setLanguage] = useState('en')
  const [input, setInput] = useState('')
  const [messages, setMessages] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [voiceAvailable, setVoiceAvailable] = useState(false)
  const [speechAvailable, setSpeechAvailable] = useState(false)
  const [voices, setVoices] = useState([])
  const [speakingMessage, setSpeakingMessage] = useState(null)
  const [speechLoadingMessage, setSpeechLoadingMessage] = useState(null)
  const recognitionRef = useRef(null)
  const messagesEndRef = useRef(null)
  const audioRef = useRef(null)
  const audioCacheRef = useRef(new Map())
  const speechOperationRef = useRef(0)

  const quickPrompts = {
    donor: [
      'What is happening with my donation?',
      'Which donation needs my attention?',
      'How is my latest delivery progressing?',
    ],
    volunteer: [
      'What should I do next?',
      'Which stop is urgent?',
      'How is my current route progressing?',
    ],
    ngo: [
      'Which donation should I prioritize?',
      'What urgent pickups need attention?',
      'Is any donation close to spoilage?',
    ],
    admin: [
      'Are there any problems I should know about?',
      'Which deliveries need intervention?',
      'What is the current operational risk?',
    ],
  }

  useEffect(() => {
    const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition
    setVoiceAvailable(Boolean(Recognition))
    setSpeechAvailable(Boolean(window.speechSynthesis && window.SpeechSynthesisUtterance))
    if (window.speechSynthesis) {
      const loadVoices = () => setVoices(window.speechSynthesis.getVoices())
      loadVoices()
      window.speechSynthesis.addEventListener?.('voiceschanged', loadVoices)
      window.speechSynthesis.onvoiceschanged = loadVoices
      return () => {
        window.speechSynthesis.removeEventListener?.('voiceschanged', loadVoices)
        if (window.speechSynthesis.onvoiceschanged === loadVoices) window.speechSynthesis.onvoiceschanged = null
        recognitionRef.current?.stop()
        window.speechSynthesis.cancel()
        audioRef.current?.pause()
        audioCacheRef.current.forEach((url) => URL.revokeObjectURL(url))
      }
    }
    return () => {
      recognitionRef.current?.stop()
      audioRef.current?.pause()
      audioCacheRef.current.forEach((url) => URL.revokeObjectURL(url))
    }
  }, [])

  useEffect(() => {
    if (open) {
      messagesEndRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
    }
  }, [messages, loading, open])

  const selectedLanguage = LANGUAGES.find((item) => item.value === language)

  const startVoiceInput = () => {
    const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition
    if (!Recognition) {
      setError('Voice input is not available in this browser.')
      return
    }
    const recognition = new Recognition()
    recognition.lang = selectedLanguage.speech
    recognition.interimResults = false
    recognition.maxAlternatives = 1
    recognition.onresult = (event) => setInput(event.results[0][0].transcript)
    recognition.onerror = () => setError('Voice input could not be completed.')
    recognition.onend = () => { recognitionRef.current = null }
    recognitionRef.current = recognition
    setError('')
    recognition.start()
  }

  const stopSpeech = () => {
    speechOperationRef.current += 1
    window.speechSynthesis?.cancel()
    if (audioRef.current) {
      audioRef.current.pause()
      audioRef.current.currentTime = 0
      audioRef.current = null
    }
    setSpeakingMessage(null)
    setSpeechLoadingMessage(null)
  }

  const speak = async (text, messageIndex) => {
    if (speakingMessage === messageIndex || speechLoadingMessage === messageIndex) {
      stopSpeech()
      return
    }
    const spokenText = cleanSpeechText(text)
    const languageCode = speechLanguage(text)
    if (!spokenText) return
    if ((!window.speechSynthesis || !window.SpeechSynthesisUtterance) && languageCode !== 'kn-IN') {
      setError('Text-to-speech is not available in this browser.')
      return
    }
    const voice = matchingVoice(voices, languageCode)
    if (languageCode === 'kn-IN' && !voice) {
      const operation = speechOperationRef.current + 1
      stopSpeech()
      speechOperationRef.current = operation
      setError('')
      setSpeechLoadingMessage(messageIndex)
      try {
        let audioUrl = audioCacheRef.current.get(spokenText)
        if (!audioUrl) {
          console.info('[FoodBridge TTS] request started', { language: languageCode, textLength: spokenText.length, endpoint: '/api/tts' })
          const audioBlob = await api.assistantKannadaAudio({ text: spokenText, language: languageCode })
          console.info('[FoodBridge TTS] audio received', { contentType: audioBlob.type, bytes: audioBlob.size })
          audioUrl = URL.createObjectURL(audioBlob)
          audioCacheRef.current.set(spokenText, audioUrl)
        }
        if (speechOperationRef.current !== operation) return
        const audio = new Audio(audioUrl)
        audioRef.current = audio
        audio.onplay = () => setSpeakingMessage(messageIndex)
        audio.onended = () => {
          if (audioRef.current === audio) audioRef.current = null
          setSpeakingMessage(null)
          setSpeechLoadingMessage(null)
        }
        audio.onerror = () => {
          if (audioRef.current === audio) audioRef.current = null
          setSpeakingMessage(null)
          setSpeechLoadingMessage(null)
          setError("Sorry, I couldn't play the Kannada audio right now. Please try again.")
        }
        await audio.play()
        setSpeechLoadingMessage(null)
      } catch (error) {
        console.error('[FoodBridge TTS] playback failed', { errorType: error?.name, message: error?.message })
        if (speechOperationRef.current === operation) {
          setSpeakingMessage(null)
          setSpeechLoadingMessage(null)
          setError("Sorry, I couldn't play the Kannada audio right now. Please try again.")
        }
      }
      return
    }
    if ((languageCode === 'hi-IN' || languageCode === 'en-IN') && !voice) {
      setError(`${languageCode === 'hi-IN' ? 'Hindi' : 'English'} voice is not available in this browser.`)
      return
    }
    window.speechSynthesis.cancel()
    if (audioRef.current) stopSpeech()
    setError('')
    const utterance = new window.SpeechSynthesisUtterance(spokenText)
    utterance.lang = languageCode
    utterance.voice = voice
    utterance.onstart = () => setSpeakingMessage(messageIndex)
    utterance.onend = () => setSpeakingMessage(null)
    utterance.onerror = () => {
      setSpeakingMessage(null)
      setError('Text-to-speech could not be completed.')
    }
    window.speechSynthesis.speak(utterance)
  }

  const submit = async (eventOrMessage) => {
    const message = typeof eventOrMessage === 'string'
      ? eventOrMessage.trim()
      : input.trim()

    if (typeof eventOrMessage !== 'string' && eventOrMessage) {
      eventOrMessage.preventDefault()
    }

    if (!message || loading) return
    setMessages((items) => [...items, { role: 'user', text: message }])
    setInput('')
    setError('')
    setLoading(true)
    try {
      const response = await api.assistantChat({ message, language })
      setMessages((items) => [...items, { role: 'assistant', text: response.reply }])
    } catch (requestError) {
      setError(requestError.message)
    } finally {
      setLoading(false)
    }
  }

  const handleQuickPrompt = (prompt) => {
    submit(prompt)
  }

  const onInputKeyDown = (event) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault()
      submit()
    }
  }

  if (!open) {
    return (
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="fixed bottom-3 right-3 z-40 flex items-center gap-2 rounded-full bg-brand-600 px-4 py-3 text-sm font-medium text-white shadow-lg hover:bg-brand-700 md:bottom-6 md:right-6"
        aria-label="Open FoodBridge assistant"
      >
        <MessageCircle size={18} /> FoodBridge Assistant
      </button>
    )
  }

  return (
    <section className="assistant-panel fixed bottom-3 right-3 z-50 flex w-[calc(100vw-24px)] flex-col overflow-hidden rounded-2xl border border-gray-200 bg-white shadow-[0_16px_40px_rgba(15,23,42,0.14)] md:bottom-6 md:right-6" aria-label="FoodBridge assistant">
      <header className="flex min-h-[4.25rem] shrink-0 items-center justify-between border-b border-gray-100 px-5 py-3">
        <div className="flex items-center gap-3">
          <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-brand-50 text-brand-700"><MessageCircle size={19} /></span>
          <div>
            <p className="font-semibold text-gray-900">FoodBridge Assistant</p>
            <p className="mt-0.5 text-xs text-gray-500">AI helper for your account</p>
          </div>
        </div>
        <button type="button" onClick={() => setOpen(false)} className="text-gray-400 hover:text-gray-700" aria-label="Close assistant">
          <X size={18} />
        </button>
      </header>

      <div className="shrink-0 border-b border-gray-100 px-5 py-3">
        <label className="text-xs font-semibold text-gray-600" htmlFor="assistant-language">Language</label>
        <select id="assistant-language" value={language} onChange={(event) => setLanguage(event.target.value)} className="input-field mt-1 h-10 py-2 text-sm">
          {LANGUAGES.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}
        </select>
        {(!voiceAvailable || !speechAvailable) && <p className="mt-2 text-xs text-gray-500">{!voiceAvailable && 'Voice input is unavailable. '}{!speechAvailable && 'Text-to-speech is unavailable.'}</p>}
      </div>

      <div className="shrink-0 border-b border-gray-100 px-5 py-3">
        <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-gray-500">Quick prompts</p>
        <div className="mt-2 flex max-h-24 flex-wrap gap-2 overflow-y-auto pr-1">
          {(quickPrompts[user?.role] || quickPrompts.donor).map((prompt) => (
            <button
              key={prompt}
              type="button"
              onClick={() => handleQuickPrompt(prompt)}
              className="rounded-full border border-gray-200 bg-gray-50 px-3 py-2 text-[13px] leading-4 text-gray-700 transition-colors hover:border-brand-200 hover:bg-brand-50 hover:text-brand-700 disabled:cursor-wait disabled:opacity-50"
              disabled={loading}
            >
              {prompt}
            </button>
          ))}
        </div>
      </div>

      <div className="assistant-messages min-h-0 flex-1 space-y-4 overflow-y-auto px-5 py-4" aria-live="polite">
        {messages.length === 0 && <p className="max-w-[90%] text-[15px] leading-6 text-gray-500">Ask about your donations, deliveries, route ETA, food risk, or demand forecast.</p>}
        {messages.map((item, index) => (
          <div key={`${item.role}-${index}`} className={item.role === 'user' ? 'ml-auto max-w-[80%] rounded-2xl rounded-br-md bg-brand-600 px-4 py-3 text-[15px] leading-6 text-white' : 'mr-auto max-w-[90%] rounded-2xl rounded-bl-md border border-gray-100 bg-gray-50 px-4 py-3 text-[15px] leading-6 text-gray-700'}>
            <div className="flex items-start justify-between gap-2">
              <div className="min-w-0 break-words">{item.role === 'assistant' ? renderAssistantMarkdown(item.text) : <p className="whitespace-pre-wrap">{item.text}</p>}</div>
              {item.role === 'assistant' && (speechAvailable || containsKannada(item.text)) && <button type="button" onClick={() => speak(item.text, index)} className={`shrink-0 transition-colors ${speakingMessage === index ? 'text-brand-700' : 'text-gray-400 hover:text-brand-700'}`} aria-label={speakingMessage === index ? 'Stop reading response' : speechLoadingMessage === index ? 'Loading audio' : 'Read response aloud'} title={speakingMessage === index ? 'Stop reading' : speechLoadingMessage === index ? 'Loading audio' : 'Read response aloud'}><Volume2 size={17} className={speakingMessage === index || speechLoadingMessage === index ? 'animate-pulse' : ''} /></button>}
            </div>
          </div>
        ))}
        {loading && <p className="text-sm text-gray-500">Checking FoodBridge data…</p>}
        <div ref={messagesEndRef} aria-hidden="true" />
      </div>

      {error && <p className="shrink-0 border-t border-gray-100 px-5 py-2 text-xs text-red-700">{error}</p>}
      <form onSubmit={submit} className="flex shrink-0 items-end gap-2 border-t border-gray-100 p-4">
        <textarea value={input} onChange={(event) => setInput(event.target.value)} onKeyDown={onInputKeyDown} rows={2} maxLength={2000} className="input-field min-h-12 flex-1 resize-none rounded-xl py-3 text-[15px] leading-5" placeholder="Ask FoodBridge…" aria-label="Message" />
        <button type="button" onClick={startVoiceInput} disabled={!voiceAvailable || loading} className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl text-gray-500 transition-colors hover:bg-gray-50 disabled:opacity-40" aria-label="Use voice input"><Mic size={19} /></button>
        <button type="submit" disabled={!input.trim() || loading} className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-brand-600 text-white transition-colors hover:bg-brand-700 disabled:opacity-40" aria-label="Send message"><Send size={19} /></button>
      </form>
    </section>
  )
}