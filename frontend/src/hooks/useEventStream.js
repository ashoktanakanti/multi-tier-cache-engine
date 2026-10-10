import { useCallback, useEffect, useRef, useState } from 'react'
import { api } from '../lib/api'

const MAX_LINES = 400

/** Incrementally polls /cache/events, keeping a bounded buffer of the newest lines. */
export function useEventStream(interval = 1000) {
  const [events, setEvents] = useState([])
  const [paused, setPaused] = useState(false)
  const lastSeq = useRef(0)

  useEffect(() => {
    if (paused) return
    let timer
    let cancelled = false
    const tick = async () => {
      try {
        const fresh = await api.events(lastSeq.current)
        if (fresh.length) {
          // A restarted backend restarts numbering: start over rather than stall.
          if (fresh[0].seq < lastSeq.current) lastSeq.current = 0
          lastSeq.current = fresh[fresh.length - 1].seq
          setEvents((prev) => [...prev, ...fresh].slice(-MAX_LINES))
        }
      } catch {
        // connection state is shown by the health indicator; keep polling
      }
      if (!cancelled) timer = setTimeout(tick, interval)
    }
    tick()
    return () => {
      cancelled = true
      clearTimeout(timer)
    }
  }, [interval, paused])

  const clear = useCallback(() => setEvents([]), [])
  return { events, paused, setPaused, clear }
}
