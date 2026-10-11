import { useRef, useState } from 'react'
import { Eraser, Square, Zap } from 'lucide-react'
import { api } from '../../lib/api'
import { fmtInt, fmtLatency, fmtPct } from '../../lib/format'
import { Button, Chip, ErrorNote, Field, Meter } from '../ui'

const ACCOUNTS = 500
const CONCURRENCY = 6 // browsers allow ~6 parallel HTTP/1.1 connections per host

function makeSampler(distribution) {
  if (distribution === 'uniform') return () => 1 + Math.floor(Math.random() * ACCOUNTS)
  // Zipf(s=1.1) over a fixed random ranking: a few accounts get most of the traffic.
  const ranking = Array.from({ length: ACCOUNTS }, (_, i) => i + 1).sort(() => Math.random() - 0.5)
  const weights = ranking.map((_, r) => 1 / (r + 1) ** 1.1)
  const total = weights.reduce((a, b) => a + b, 0)
  const cdf = []
  weights.reduce((acc, w, i) => (cdf[i] = acc + w / total), 0)
  return () => {
    const u = Math.random()
    let lo = 0
    let hi = cdf.length - 1
    while (lo < hi) {
      const mid = (lo + hi) >> 1
      if (cdf[mid] < u) lo = mid + 1
      else hi = mid
    }
    return ranking[lo]
  }
}

const emptyRun = () => ({ done: 0, bySource: {}, msBySource: {} })

export default function LoadTab({ onReset }) {
  const [count, setCount] = useState(300)
  const [distribution, setDistribution] = useState('zipf')
  const [run, setRun] = useState(null)
  const [running, setRunning] = useState(false)
  const [error, setError] = useState(null)
  const stopRef = useRef(false)

  const start = async () => {
    stopRef.current = false
    setRunning(true)
    setError(null)
    const sample = makeSampler(distribution)
    const acc = emptyRun()
    setRun({ ...acc, total: count })
    let issued = 0

    const worker = async () => {
      while (!stopRef.current && issued < count) {
        issued++
        try {
          const { source, ms } = await api.summary(sample())
          const s = (source || '?').toLowerCase()
          acc.bySource[s] = (acc.bySource[s] ?? 0) + 1
          acc.msBySource[s] = (acc.msBySource[s] ?? 0) + ms
        } catch (err) {
          if (err.status !== 404) {
            setError(err)
            stopRef.current = true
          }
        }
        acc.done++
        if (acc.done % 10 === 0 || acc.done === count) setRun({ ...acc, total: count })
      }
    }
    await Promise.all(Array.from({ length: CONCURRENCY }, worker))
    setRun({ ...acc, total: count })
    setRunning(false)
  }

  const reset = async () => {
    try {
      await api.clearCache()
      setRun(null)
      onReset?.()
    } catch (err) {
      setError(err)
    }
  }

  const hits = run ? (run.bySource.l1 ?? 0) + (run.bySource.l2 ?? 0) : 0
  const served = run ? Object.values(run.bySource).reduce((a, b) => a + b, 0) : 0

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-end gap-3">
        <Field label="Requests">
          <div className="flex gap-1">
            {[100, 300, 1000].map((n) => (
              <Chip key={n} active={count === n} onClick={() => setCount(n)}>{n}</Chip>
            ))}
          </div>
        </Field>
        <Field label="Access pattern">
          <div className="flex gap-1">
            <Chip active={distribution === 'zipf'} onClick={() => setDistribution('zipf')}>Zipf (hot set)</Chip>
            <Chip active={distribution === 'uniform'} onClick={() => setDistribution('uniform')}>Uniform</Chip>
          </div>
        </Field>
        <div className="ml-auto flex gap-1.5">
          <Button size="sm" variant="ghost" icon={Eraser} onClick={reset} disabled={running}>Clear L1 + stats</Button>
          {running ? (
            <Button size="sm" variant="ghost" icon={Square} onClick={() => (stopRef.current = true)}>Stop</Button>
          ) : (
            <Button size="sm" variant="primary" icon={Zap} onClick={start}>Run</Button>
          )}
        </div>
      </div>

      <ErrorNote error={error} />

      {run && (
        <div className="border border-line rounded">
          <div className="px-2.5 py-2 space-y-1.5 border-b border-line">
            <div className="flex justify-between font-mono text-[11px]">
              <span className="text-fg-muted">{fmtInt(run.done)} / {fmtInt(run.total)} requests</span>
              <span className="text-accent">{fmtPct(served ? hits / served : 0)} hit</span>
            </div>
            <Meter value={run.done} max={run.total} />
          </div>
          <table className="w-full font-mono text-[11.5px]">
            <thead>
              <tr className="text-[10px] uppercase tracking-[0.08em] text-fg-faint font-sans">
                <th className="text-left font-medium px-2.5 h-7">answered by</th>
                <th className="text-right font-medium px-2">requests</th>
                <th className="text-right font-medium px-2">share</th>
                <th className="text-right font-medium px-2.5">avg server time</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line border-t border-line">
              {['l1', 'l2', 'db'].filter((s) => run.bySource[s]).map((s) => (
                <tr key={s}>
                  <td className="px-2.5 h-7 uppercase">{s}</td>
                  <td className="px-2 text-right">{fmtInt(run.bySource[s])}</td>
                  <td className="px-2 text-right text-fg-muted">{fmtPct(run.bySource[s] / served)}</td>
                  <td className="px-2.5 text-right">{fmtLatency(run.msBySource[s] / run.bySource[s])}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <p className="text-[11.5px] text-fg-dim leading-5">
        Fires real requests at <span className="font-mono text-fg-muted">/accounts/:id/summary</span> ({CONCURRENCY} at a time).
        With the hot-set pattern a few accounts get most of the traffic, so the hit ratio climbs quickly. With the uniform
        pattern the 500 accounts don&rsquo;t fit in a 256-entry L1, so many requests still go to the database.
      </p>
    </div>
  )
}
