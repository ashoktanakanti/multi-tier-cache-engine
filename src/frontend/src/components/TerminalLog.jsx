import { useEffect, useMemo, useRef, useState } from 'react'
import { ChevronDown, ChevronUp, Pause, Play, TerminalSquare, Trash2 } from 'lucide-react'
import { cx, fmtClock, fmtLatency } from '../lib/format'
import { Button, Chip } from './ui'

const FILTERS = {
  all: () => true,
  hits: (e) => e.kind === 'hit',
  db: (e) => e.kind === 'load',
  evict: (e) => ['evict', 'expire', 'clear'].includes(e.kind),
  writes: (e) => e.kind === 'invalidate' || e.kind === 'stale_skip',
}

const KINDS = {
  hit: { tag: 'HIT', tone: 'text-accent', detail: (e) => `served from ${e.tier.toUpperCase()}` },
  load: { tag: 'MISS', tone: 'text-fg', detail: () => 'read from database → stored in cache' },
  evict: { tag: 'EVICT', tone: 'text-fg-muted', detail: (e) => e.detail },
  invalidate: { tag: 'INVAL', tone: 'text-fg', detail: () => 'write committed → cached copy deleted' },
  clear: { tag: 'CLEAR', tone: 'text-fg-muted', detail: (e) => e.detail },
  expire: { tag: 'EXPIRE', tone: 'text-fg-muted', detail: (e) => `L1 copy ${e.detail} → removed` },
  stale_skip: { tag: 'GUARD', tone: 'text-accent', detail: (e) => e.detail },
}

function describe(e) {
  const k = KINDS[e.kind] ?? { tag: e.kind.toUpperCase(), tone: 'text-fg-muted', detail: () => '' }
  return { tag: k.tag, tone: k.tone, detail: k.detail(e) }
}

export default function TerminalLog({ events, paused, setPaused, clear, open, setOpen }) {
  const [filter, setFilter] = useState('all')
  const scrollRef = useRef(null)
  const stickRef = useRef(true)
  const lines = useMemo(() => events.filter(FILTERS[filter]), [events, filter])

  useEffect(() => {
    const el = scrollRef.current
    if (el && stickRef.current) el.scrollTop = el.scrollHeight
  }, [lines, open])

  const onScroll = () => {
    const el = scrollRef.current
    stickRef.current = el.scrollHeight - el.scrollTop - el.clientHeight < 24
  }

  return (
    <section className="shrink-0 border-t border-line bg-ink-950">
      <header className="h-9 flex items-center gap-2 px-3 sm:px-4">
        <button onClick={() => setOpen(!open)} className="flex items-center gap-2 text-[12px] font-semibold hover:text-fg text-fg-muted">
          <TerminalSquare size={14} strokeWidth={1.75} />
          Engine log
          {open ? <ChevronDown size={13} /> : <ChevronUp size={13} />}
        </button>
        <span className="font-mono text-[10.5px] text-fg-faint">{events.length} lines</span>
        {!paused && <span className="size-1.5 rounded-full bg-up animate-pulse" title="streaming" />}
        {open && (
          <div className="ml-auto flex items-center gap-1 overflow-x-auto">
            {Object.keys(FILTERS).map((f) => (
              <Chip key={f} active={filter === f} onClick={() => setFilter(f)} className="uppercase !h-5 !px-2 !text-[10px]">{f}</Chip>
            ))}
            <span className="w-px h-4 bg-line mx-1" />
            <Button size="sm" variant="subtle" icon={paused ? Play : Pause} onClick={() => setPaused(!paused)}>
              <span className="hidden sm:inline">{paused ? 'Resume' : 'Pause'}</span>
            </Button>
            <Button size="sm" variant="subtle" icon={Trash2} onClick={clear}><span className="hidden sm:inline">Clear</span></Button>
          </div>
        )}
      </header>
      {open && (
        <div ref={scrollRef} onScroll={onScroll} className="h-[200px] overflow-y-auto border-t border-line px-3 sm:px-4 py-1.5 font-mono text-[11.5px] leading-[19px] bg-[#070708]">
          {lines.length === 0 && <div className="text-fg-faint">waiting for cache activity… try READ KEY or generate traffic in STATS.</div>}
          {lines.map((e) => {
            const d = describe(e)
            return (
              <div key={e.seq} className="flex gap-3 whitespace-nowrap hover:bg-ink-900">
                <span className="text-fg-faint">{fmtClock(e.ts)}</span>
                <span className={cx('w-12 shrink-0', d.tone)}>{d.tag}</span>
                <span className="w-[170px] shrink-0 truncate text-fg-muted">{e.key ?? '—'}</span>
                <span className="w-[70px] shrink-0 text-right text-fg">{e.ms != null ? fmtLatency(e.ms) : ''}</span>
                <span className="text-fg-dim truncate">{d.detail}</span>
              </div>
            )
          })}
        </div>
      )}
    </section>
  )
}
