import { BookOpen, Scale } from 'lucide-react'
import { Panel, PanelHeader } from '../components/ui'

const WHY = [
  ['Expensive', 'A summary joins every holding to its latest price and adds up a year of daily values. That takes about 25 ms in SQL, versus a few microseconds from L1.'],
  ['Read a lot', 'Dashboards and reports read the same accounts again and again. Trades and price updates are rare by comparison.'],
  ['Changes at known moments', 'A summary only changes when the account trades or a price is updated. Both go through our service, so we know exactly which keys to delete.'],
  ['Some accounts are popular', 'A few large clients get most of the traffic, so a small L1 can still answer most requests.'],
]

const DECISIONS = [
  ['Why two cache tiers?', 'L1 is the fastest (no network) but each server process has its own. L2 (Redis) is shared by every process and survives restarts.'],
  ['LRU or LFU?', 'LRU keeps recently used keys and adapts fast when popularity shifts. LFU keeps frequently used keys, so a burst of one-off reads can’t push out a popular account. Both are O(1), and you choose with CACHE_POLICY.'],
  ['Cache-aside', 'The cache is only filled when someone reads, so accounts nobody looks at never take up space. The cost is a slow first read.'],
  ['Delete on write', 'After a trade commits, we delete the cached summary instead of updating it. The next read rebuilds it from the database, so it can’t be wrong.'],
  ['TTL on Redis', 'Every Redis entry expires after 5 minutes, as a safety net in case an invalidation is ever missed.'],
  ['Fail-open', 'If Redis is down, its errors count as cache misses and requests go to the database. The cache should speed the app up, never break it.'],
]

const NOT = [
  'Tick-by-tick live prices: data changes faster than a cached copy could be reused.',
  'Random access over many more keys than fit in the cache (see the Benchmark page).',
  'Write-heavy data: every write deletes the cached copy before anyone reads it.',
  'Cheap queries: a 0.1 ms lookup by primary key doesn’t need a cache at all.',
]

const FUTURE = [
  'Request coalescing: when many requests miss the same key at once, run the DB query only once.',
  'Redis pub/sub so every server clears its own L1 when another server writes.',
]

export default function DesignView() {
  return (
    <div className="grid gap-3 xl:grid-cols-2 items-start">
      <Panel>
        <PanelHeader title="Why cache account summaries?" icon={BookOpen} />
        <dl className="divide-y divide-line">
          {WHY.map(([k, v]) => (
            <div key={k} className="grid grid-cols-[150px_minmax(0,1fr)] gap-3 px-3 py-2.5">
              <dt className="text-[12px] font-semibold text-accent">{k}</dt>
              <dd className="text-[12px] text-fg-muted leading-5">{v}</dd>
            </div>
          ))}
        </dl>
        <div className="border-t border-line px-3 py-2.5">
          <div className="text-[10px] uppercase tracking-[0.1em] text-fg-faint mb-1.5">When a cache would NOT be worth it</div>
          <ul className="space-y-1">
            {NOT.map((n) => (
              <li key={n} className="text-[12px] text-fg-muted leading-5 flex gap-2"><span className="text-fg-faint font-mono">—</span>{n}</li>
            ))}
          </ul>
        </div>
      </Panel>

      <Panel>
        <PanelHeader title="Design decisions" icon={Scale} />
        <dl className="divide-y divide-line">
          {DECISIONS.map(([k, v]) => (
            <div key={k} className="grid grid-cols-[150px_minmax(0,1fr)] gap-3 px-3 py-2.5">
              <dt className="text-[12px] font-semibold">{k}</dt>
              <dd className="text-[12px] text-fg-muted leading-5">{v}</dd>
            </div>
          ))}
        </dl>
        <div className="border-t border-line px-3 py-2.5">
          <div className="text-[10px] uppercase tracking-[0.1em] text-fg-faint mb-1.5">Possible next steps</div>
          <ul className="space-y-1">
            {FUTURE.map((n) => (
              <li key={n} className="text-[12px] text-fg-muted leading-5 flex gap-2"><span className="text-fg-faint font-mono">+</span>{n}</li>
            ))}
          </ul>
        </div>
      </Panel>
    </div>
  )
}
