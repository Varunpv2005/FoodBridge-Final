import { useEffect, useRef, useState } from 'react'
import { wsUrl } from '../api/client'

export function useTrackingSocket(channel) {
  const [lastMessage, setLastMessage] = useState(null)
  const [connected, setConnected] = useState(false)
  const wsRef = useRef(null)
  const pendingMessageRef = useRef(null)

  useEffect(() => {
    if (!channel) return undefined
    let stopped = false
    let reconnectTimer

    const connect = () => {
      if (stopped) return
      if (wsRef.current && (wsRef.current.readyState === WebSocket.CONNECTING || wsRef.current.readyState === WebSocket.OPEN)) return
      const ws = new WebSocket(wsUrl(channel))
      wsRef.current = ws
      ws.onopen = () => {
        setConnected(true)
        if (pendingMessageRef.current) {
          ws.send(JSON.stringify(pendingMessageRef.current))
          pendingMessageRef.current = null
        }
      }
      ws.onmessage = (evt) => {
        try { setLastMessage(JSON.parse(evt.data)) } catch { /* ignore malformed events */ }
      }
      ws.onclose = () => {
        setConnected(false)
        if (wsRef.current === ws && ws.code === 1008) {
          window.dispatchEvent(new Event('foodbridge:unauthorized'))
          return
        }
        if (!stopped) reconnectTimer = setTimeout(connect, 1000)
      }
    }

    connect()

    return () => {
      stopped = true
      clearTimeout(reconnectTimer)
      if (wsRef.current && wsRef.current.readyState < WebSocket.CLOSING) wsRef.current.close()
      wsRef.current = null
      setConnected(false)
      pendingMessageRef.current = null
    }
  }, [channel])

  const send = (message) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(message))
      return true
    }
    if (message?.type !== 'location_update') pendingMessageRef.current = message
    return false
  }

  return { lastMessage, send, connected }
}
