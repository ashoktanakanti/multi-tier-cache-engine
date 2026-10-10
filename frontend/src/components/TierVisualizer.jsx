import { ArrowDown, ArrowUp, Cpu, Database, Server } from 'lucide-react'
import { cx, fmtBytes, fmtInt, fmtLatency, fmtPct } from '../lib/format'
import { Meter, Panel, PanelHeader } from './ui'

function TierRow({ code, name, tech, icon: Icon, disabled, capacity, served, servedLabel, reached, lat, highlight }) {
  // Local hit rate: of the requests that reached this tier, how many it answered.
  const localRate = reached ? served / reached : null
  return (
    <div className={cx('grid grid-cols-[52px_minmax(0,1fr)] sm:grid-cols-[52px_minmax(0,1.3fr)_minmax(0,1fr)_minmax(0,1fr)] gap-x-3 gap-y-2 px-3 py-3', disabled && 'opacity-45', highlight && 'animate-flash')}>
      <div className="row-span-3 sm:row-span-1 flex flex-col items-center justify-center rounded border border-line bg-ink-850 h-[52px]">
        <span className="font-mono text-[15px] font-semibold">{code}</span>
        <Icon size={12} className="text-fg-dim mt-0.5" strokeWidth={1.75} />
      </div>

      <div className="min-w-0 self-center">
        <div className="text-[12.5px] font-semibold truncate">{name}</div>
        <div className="text-[11px] text-fg-dim truncate">{tech}</div>
        <div className="mt-1.5 space-y-1">
          <Meter value={capacity.value ?? 0} max={capacity.max || 1} tone={capacity.max ? 'accent' : 'dim'} />
          <div className="font-mono text-[10.5px] text-fg-dim truncate">{capacity.label}</div>
        </div>
      </div>

      <div className="min-w-0 self-center font-mono">
        <div className="text-[10px] uppercase tracking-[0.1em] text-fg-faint font-sans">{servedLabel}</div>
        <div className="text-[15px]">{disabled ? '—' : fmtInt(served)}</div>
        <div className="text-[10.5px] text-fg-dim">
          {disabled ? 'tier off' : code === 'L3' ? 'answers every miss' : `hit rate here ${fmtPct(localRate)}`}
        </div>
      </div>

      <div className="min-w-0 self-center font-mono">
        <div className="text-[10px] uppercase tracking-[0.1em] text-fg-faint font-sans">read latency p50</div>
        <div className="text-[15px]">{fmtLatency(lat?.p50)}</div>
        <div className="text-[10.5px] text-fg-dim">p95 {fmtLatency(lat?.p95)}</div>
      </div>
    </div>
  )
}

function Connector({ disabled }) {
  return (
    <div className={cx('flex items-center gap-3 px-3 h-6 border-y border-line bg-ink-950/60 font-mono text-[10px] text-fg-faint', disabled && 'opacity-45')}>
      <span className="w-[52px]" />
      <span className="inline-flex items-center gap-1"><ArrowDown size={11} /> miss → next tier</span>
      <span className="inline-flex items-center gap-1 ml-auto"><ArrowUp size={11} className="text-accent" /> value copied back up</span>
    </div>
  )
}

export default function TierVisualizer({ stats, redis, flashTier }) {
  const hits = stats?.hits ?? {}
  const lat = stats?.latency_ms ?? {}
  const total = stats?.requests ?? 0
  const l1 = stats?.l1
  const l2 = stats?.l2
  const reachedL2 = total - (hits.l1 ?? 0)
  const reachedDb = reachedL2 - (hits.l2 ?? 0)
  const policy = stats?.policy?.toUpperCase() ?? ''

  return (
    <Panel>
      <PanelHeader title="Cache tiers" icon={Server} meta="read path: top → bottom" />

      <TierRow
        code="L1" icon={Cpu} name="In-memory cache" highlight={flashTier === 'l1'}
        tech={`hand-built ${policy} · hash map + linked list · inside the API process`}
        capacity={{ value: l1?.size, max: l1?.capacity, label: `${fmtInt(l1?.size)} / ${fmtInt(l1?.capacity)} entries` }}
        served={hits.l1 ?? 0} servedLabel="hits" reached={total} lat={lat.l1}
      />
      <Connector />
      <TierRow
        code="L2" icon={Server} name="Redis (shared)" disabled={!l2} highlight={flashTier === 'l2'}
        tech={redis === 'in-memory fake' ? 'fake in-memory Redis (dev mode — no network delay)' : 'Redis · JSON values · TTL expiry'}
        capacity={{ value: 0, max: 0, label: l2 ? `${fmtInt(l2.keys)} ${l2.keys === 1 ? 'key' : 'keys'} · TTL ${l2.ttl}s` : 'not configured — set REDIS_URL' }}
        served={hits.l2 ?? 0} servedLabel="hits" reached={reachedL2} lat={lat.l2}
      />
      <Connector disabled={!l2} />
      <TierRow
        code="L3" icon={Database} name="Database (source of truth)" highlight={flashTier === 'db'}
        tech="SQLite · holdings × prices join + 1-year history"
        capacity={{ value: 0, max: 0, label: `${fmtBytes(stats?.db_size_bytes)} on disk · all writes go here` }}
        served={hits.db ?? 0} servedLabel="queries" reached={reachedDb} lat={lat.db}
      />
    </Panel>
  )
}
