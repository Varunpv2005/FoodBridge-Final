import { useEffect, useRef, useState } from 'react'
import { wsUrl } from '../api/client'

export function useTrackingSocket(channel) {
  const [lastMessage, setLastMessage] = useState(null)
  const wsRef = useRef(null)

  useEffect(() => {
    if (!channel) return undefined
    let closed = false
    let ws

    try {
      ws = new WebSocket(wsUrl(channel))
      wsRef.current = ws
      ws.onmessage = (evt) => {
        try { setLastMessage(JSON.parse(evt.data)) } catch { /* ignore */ }
      }
      ws.onerror = () => {}
    } catch {
      /* WebSocket unsupported / connection refused -- dashboard still works without live push */
    }

    return () => {
      closed = true
      if (ws && ws.readyState === WebSocket.OPEN) ws.close()
    }
  }, [channel])

  return lastMessage
}
