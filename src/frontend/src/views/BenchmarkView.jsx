import { Gauge } from 'lucide-react'
import { usePolling } from '../hooks/usePolling'
import { api } from '../lib/api'
import { cx, fmtInt, fmtLatency, fmtPct } from '../lib/format'
import { ErrorNote, Panel, PanelHeader } from '../components/ui'

const PATTERNS = {
  popular: {
    title: 'Popular accounts (realistic)',
    blurb: 'A few accounts get most of the traffic, like real client dashboards. This is the case caching is built for.',
  },
  random: {
    title: 'Random accounts',
    blurb: 'Every account is equally likely and only 64 of 500 fit in L1. Nothing is "hot", so the cache rarely helps.',
  },
  writes: {
    title: 'Half the operations are trades',
    blurb: 'Every trade deletes a cached summary, so many reads find nothing and go to the database.',
  },
}

const SETUP_LABEL = { no_cache: 'No cache', lru: 'L1 · LRU', lfu: 'L1 · LFU' }

function PatternCard({ id, rows }) {
  const meta = PATTERNS[id]
  const base = rows.no_cache
  const best = ['lru', 'lfu'].map((k) => rows[k]).sort((a, b) => b.hit_ratio - a.hit_ratio)[0]
  const saved = 1 - best.db_queries / base.db_queries
  const maxAvg = Math.max(...Object.values(rows).map((r) => r.avg_ms))

  return (
    <Panel>
      <div className="px-3 py-2.5 border-b border-line flex items-start gap-3">
        <div className="min-w-0">
          <h3 className="text-[13px] font-semibold">{meta.title}</h3>
          <p className="text-[11.5px] text-fg-dim mt-0.5">{meta.blurb}</p>
        </div>
        <div className="ml-auto text-right shrink-0 font-mono">
          <div className={cx('text-[18px]', saved >= 0.5 ? 'text-accent' : 'text-fg')}>{fmtPct(saved, 0)}</div>
          <div className="text-[10.5px] text-fg-dim">fewer DB queries</div>
        </div>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full font-mono text-[11.5px] min-w-[560px]">
          <thead>
            <tr className="text-[10px] uppercase tracking-[0.08em] text-fg-faint font-sans border-b border-line">
              <th className="text-left font-medium px-3 h-7">setup</th>
              <th className="text-right font-medium px-2">hit ratio</th>
              <th className="text-right font-medium px-2">db queries</th>
              <th className="text-right font-medium px-2">p50 read</th>
              <th className="text-left font-medium px-3 w-[34%]">average read</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-line">
            {Object.entries(rows).map(([setup, r]) => (
              <tr key={setup}>
                <td className="px-3 h-8 font-sans text-[12px]">{SETUP_LABEL[setup] ?? setup}</td>
                <td className="px-2 text-right">{fmtPct(r.hit_ratio)}</td>
                <td className="px-2 text-right text-fg-muted">{fmtInt(r.db_queries)} / {fmtInt(r.reads)}</td>
                <td className="px-2 text-right">{fmtLatency(r.p50_ms)}</td>
                <td className="px-3">
                  <div className="flex items-center gap-2">
                    <div className="h-1.5 flex-1 bg-ink-800 rounded-full overflow-hidden">
                      <div className={cx('h-full rounded-full', setup === 'no_cache' ? 'bg-fg-faint' : 'bg-accent')}
                        style={{ width: `${(r.avg_ms / maxAvg) * 100}%` }} />
                    </div>
                    <span className="w-16 text-right text-fg-muted">{fmtLatency(r.avg_ms)}</span>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Panel>
  )
}

export default function BenchmarkView() {
  const { data, error } = usePolling(api.benchmark, 15000)

  if (error?.status === 404) {
    return (
      <Panel className="p-6 text-center">
        <p className="text-fg-muted">No benchmark results yet.</p>
        <p className="font-mono text-[12px] text-fg-dim mt-2">python benchmark.py</p>
      </Panel>
    )
  }
  if (!data) return <ErrorNote error={error} />

  return (
    <div className="space-y-3">
      <Panel>
        <PanelHeader title="Benchmark results" icon={Gauge} meta={`run ${new Date(data.generated_at).toLocaleString()}`} />
        <dl className="grid grid-cols-3 divide-x divide-line font-mono text-[11.5px]">
          {[
            ['operations per run', fmtInt(data.operations)],
            ['accounts', fmtInt(data.accounts)],
            ['L1 capacity', fmtInt(data.l1_capacity)],
          ].map(([k, v]) => (
            <div key={k} className="px-3 py-2">
              <dt className="text-[10px] uppercase tracking-[0.1em] text-fg-faint font-sans">{k}</dt>
              <dd>{v}</dd>
            </div>
          ))}
        </dl>
        <p className="border-t border-line px-3 py-2 text-[11.5px] text-fg-dim">
          The p50 column compares a typical cache hit with a typical database query. The average includes the misses,
          so it can only improve as much as the hit ratio allows. Timings vary from run to run on a laptop; hit ratio
          and DB query counts don&rsquo;t.
        </p>
      </Panel>
      {Object.keys(PATTERNS).filter((k) => data.results[k]).map((k) => <PatternCard key={k} id={k} rows={data.results[k]} />)}
    </div>
  )
}
