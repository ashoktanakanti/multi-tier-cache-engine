import { cx, fmtLatency } from '../../lib/format'

const TIER_LABEL = { l1: 'L1', l2: 'L2', db: 'L3' }

function tone(result) {
  if (result === 'hit') return 'text-accent'
  if (result === 'miss' || result === 'not found') return 'text-fg-dim'
  return 'text-fg'
}

/**
 * Shows each step of a real lookup one after another.
 * The animation delay is only for readability; every time shown is measured.
 */
export default function TraceSteps({ steps, runId }) {
  const total = steps.reduce((sum, s) => sum + s.ms, 0) || 1
  let cumulative = 0
  return (
    <ol className="font-mono text-[11.5px] border border-line rounded divide-y divide-line">
      <li className="grid grid-cols-[22px_30px_minmax(0,1fr)_72px_72px] gap-2 px-2.5 h-7 items-center text-[10px] uppercase tracking-[0.08em] text-fg-faint font-sans">
        <span>#</span><span>tier</span><span>operation</span><span className="text-right">step</span><span className="text-right">total</span>
      </li>
      {steps.map((s, i) => {
        cumulative += s.ms
        return (
          <li key={`${runId}-${i}`} className="animate-step-in px-2.5 py-1.5" style={{ animationDelay: `${i * 110}ms` }}>
            <div className="grid grid-cols-[22px_30px_minmax(0,1fr)_72px_72px] gap-2 items-center">
              <span className="text-fg-faint">{String(i + 1).padStart(2, '0')}</span>
              <span className="text-fg-muted">{TIER_LABEL[s.tier] ?? s.tier}</span>
              <span className="truncate">
                <span className="text-fg-muted">{s.op}</span>
                <span className="text-fg-faint"> → </span>
                <span className={tone(s.result)}>{s.result}</span>
              </span>
              <span className="text-right">{fmtLatency(s.ms)}</span>
              <span className="text-right text-fg-dim">{fmtLatency(cumulative)}</span>
            </div>
            <div className="ml-[62px] mt-1 h-[3px] bg-ink-800 rounded-full overflow-hidden">
              <div
                className={cx('h-full rounded-full', s.result === 'hit' ? 'bg-accent' : 'bg-fg-faint')}
                style={{ width: `${Math.max(1.5, (s.ms / total) * 100)}%` }}
              />
            </div>
          </li>
        )
      })}
    </ol>
  )
}
