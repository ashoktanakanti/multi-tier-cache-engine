import { fmtLatency } from '../../lib/format'

/** What a write actually did: commit to the database first, then delete the cached copies. */
export default function WritePath({ result, redis, runId }) {
  const l2On = redis && redis !== 'disabled'
  const steps = [
    { tier: 'L3', op: 'SQL transaction', result: 'committed', ms: result.db_ms },
    { tier: 'L1', op: 'delete key', result: 'removed', ms: null },
    { tier: 'L2', op: l2On ? 'DEL key' : 'skipped', result: l2On ? 'removed' : 'no Redis', ms: null },
  ]
  return (
    <ol className="font-mono text-[11.5px] border border-line rounded divide-y divide-line">
      {steps.map((s, i) => (
        <li key={`${runId}-${i}`} className="animate-step-in grid grid-cols-[22px_30px_minmax(0,1fr)_72px] gap-2 px-2.5 h-8 items-center"
          style={{ animationDelay: `${i * 110}ms` }}>
          <span className="text-fg-faint">{String(i + 1).padStart(2, '0')}</span>
          <span className="text-fg-muted">{s.tier}</span>
          <span className="truncate">
            <span className="text-fg-muted">{s.op}</span>
            <span className="text-fg-faint"> → </span>
            <span>{s.result}</span>
          </span>
          <span className="text-right">{s.ms != null ? fmtLatency(s.ms) : ''}</span>
        </li>
      ))}
      <li className="animate-step-in px-2.5 h-8 flex items-center justify-between text-[11px]" style={{ animationDelay: '330ms' }}>
        <span className="text-fg-dim">cache invalidation (L1 + L2)</span>
        <span>{fmtLatency(result.invalidate_ms)}</span>
      </li>
    </ol>
  )
}
