import { fmtInt, fmtLatency, fmtPct } from '../lib/format'
import { Stat } from './ui'

export default function MetricsBar({ stats }) {
  const hits = stats?.hits ?? {}
  const lat = stats?.latency_ms ?? {}
  const requests = stats?.requests ?? 0
  const l1 = lat.l1?.p50
  const dbP50 = lat.db?.p50
  const speedup = l1 && dbP50 ? dbP50 / l1 : null

  const cells = [
    { label: 'Requests', value: fmtInt(stats?.requests), sub: 'since reset' },
    { label: 'Hit ratio', value: fmtPct(stats?.hit_ratio), sub: `${fmtInt((hits.l1 ?? 0) + (hits.l2 ?? 0))} served from cache`, accent: true },
    { label: 'DB queries', value: fmtInt(hits.db), sub: `${fmtPct(requests ? (hits.db ?? 0) / requests : null)} of requests` },
    { label: 'L1 hit p50', value: fmtLatency(l1), sub: `p95 ${fmtLatency(lat.l1?.p95)}` },
    { label: 'DB query p50', value: fmtLatency(dbP50), sub: `p95 ${fmtLatency(lat.db?.p95)}` },
    { label: 'L1 vs DB', value: speedup ? `${fmtInt(Math.round(speedup))}×` : '—', sub: 'faster at p50', accent: !!speedup },
    { label: 'Invalidations', value: fmtInt(stats?.invalidations), sub: 'keys dropped on writes' },
    { label: 'Evictions', value: fmtInt(stats?.evictions), sub: `${stats?.policy?.toUpperCase() ?? ''} · L1 full` },
  ]

  return (
    <div className="grid grid-cols-2 sm:grid-cols-4 xl:grid-cols-8 border border-line rounded-md bg-ink-900 [&>*]:border-line [&>*]:border-b xl:[&>*]:border-b-0 [&>*:not(:last-child)]:border-r">
      {cells.map((c) => (
        <Stat key={c.label} {...c} />
      ))}
    </div>
  )
}
