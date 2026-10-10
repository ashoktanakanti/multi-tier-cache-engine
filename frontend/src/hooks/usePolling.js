import { useCallback, useEffect, useRef, useState } from 'react'

/**
 * Calls `fn` every `interval` ms while the tab is visible.
 * Keeps the last good value on error so the UI doesn't flicker on a blip.
 */
export function usePolling(fn, interval, { enabled = true } = {}) {
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  const fnRef = useRef(fn)
  fnRef.current = fn

  const refresh = useCallback(async () => {
    try {
      setData(await fnRef.current())
      setError(null)
    } catch (err) {
      setError(err)
    }
  }, [])

  useEffect(() => {
    if (!enabled) return
    let timer
    let cancelled = false
    const tick = async () => {
      if (document.visibilityState === 'visible') await refresh()
      if (!cancelled) timer = setTimeout(tick, interval)
    }
    tick()
    return () => {
      cancelled = true
      clearTimeout(timer)
    }
  }, [interval, enabled, refresh])

  return { data, error, refresh }
}
