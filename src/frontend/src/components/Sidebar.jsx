import { BookOpen, Gauge, Layers, ListTree, X } from 'lucide-react'
import { cx } from '../lib/format'
import { Dot, SectionLabel } from './ui'

export const NAV = [
  { section: 'Engine', items: [
    { id: 'overview', label: 'Overview', icon: Layers },
    { id: 'accounts', label: 'Accounts', icon: ListTree },
  ] },
  { section: 'Analysis', items: [
    { id: 'benchmark', label: 'Benchmark', icon: Gauge },
    { id: 'design', label: 'Design notes', icon: BookOpen },
  ] },
]

function Logo() {
  return (
    <svg width="22" height="22" viewBox="0 0 22 22" aria-hidden="true">
      <rect x="0.5" y="0.5" width="21" height="21" rx="4" fill="#0e0e11" stroke="#27272a" />
      <rect x="5" y="5.5" width="12" height="2.5" rx="0.5" fill="#f59e0b" />
      <rect x="5" y="9.75" width="8.5" height="2.5" rx="0.5" fill="#a1a1aa" />
      <rect x="5" y="14" width="5" height="2.5" rx="0.5" fill="#52525b" />
    </svg>
  )
}

export default function Sidebar({ view, onNavigate, health, stats, open, onClose }) {
  const apiUp = !!health
  const redis = health?.redis

  return (
    <>
      {open && <div className="fixed inset-0 z-30 bg-black/60 lg:hidden" onClick={onClose} />}
      <aside
        className={cx(
          'fixed lg:static z-40 inset-y-0 left-0 w-[220px] shrink-0 flex flex-col border-r border-line bg-ink-950 transition-transform lg:translate-x-0',
          open ? 'translate-x-0' : '-translate-x-full',
        )}
      >
        <div className="h-12 flex items-center gap-2.5 px-3 border-b border-line">
          <Logo />
          <div className="leading-tight">
            <div className="text-[13px] font-semibold tracking-tight">Cache Terminal</div>
            <div className="text-[10px] text-fg-dim font-mono">portfolio-valuation v2</div>
          </div>
          <button className="ml-auto lg:hidden text-fg-dim hover:text-fg" onClick={onClose} aria-label="Close menu">
            <X size={16} />
          </button>
        </div>

        <nav className="flex-1 overflow-y-auto pb-3">
          {NAV.map(({ section, items }) => (
            <div key={section}>
              <SectionLabel>{section}</SectionLabel>
              <ul className="px-2 space-y-0.5">
                {items.map(({ id, label, icon: Icon }) => {
                  const active = view === id
                  return (
                    <li key={id}>
                      <button
                        onClick={() => onNavigate(id)}
                        className={cx(
                          'w-full h-8 flex items-center gap-2.5 px-2.5 rounded text-[12.5px] transition-colors',
                          active ? 'bg-accent text-ink-950 font-semibold' : 'text-fg-muted hover:text-fg hover:bg-ink-800',
                        )}
                      >
                        <Icon size={15} strokeWidth={active ? 2.25 : 1.75} />
                        {label}
                      </button>
                    </li>
                  )
                })}
              </ul>
            </div>
          ))}

          <SectionLabel>Configuration</SectionLabel>
          <dl className="mx-3 border border-line rounded font-mono text-[11px] divide-y divide-line">
            {[
              ['policy', health?.policy?.toUpperCase() ?? '—'],
              ['l1.capacity', stats?.l1?.capacity ?? '—'],
              ['l1.ttl', stats?.l1?.ttl ? `${stats.l1.ttl}s` : 'off'],
              ['l2.ttl', stats?.l2 ? `${stats.l2.ttl}s` : 'off'],
              ['database', 'SQLite'],
            ].map(([k, v]) => (
              <div key={k} className="flex justify-between px-2.5 h-7 items-center">
                <dt className="text-fg-dim">{k}</dt>
                <dd className="text-fg">{v}</dd>
              </div>
            ))}
          </dl>
        </nav>

        <div className="border-t border-line px-3 py-2.5 space-y-1.5 font-mono text-[11px]">
          <div className="flex items-center gap-2">
            <Dot tone={apiUp ? 'ok' : 'err'} />
            <span className="text-fg-muted">api</span>
            <span className="ml-auto text-fg-dim">{apiUp ? 'connected' : 'offline'}</span>
          </div>
          <div className="flex items-center gap-2">
            <Dot tone={redis === 'connected' ? 'ok' : redis === 'in-memory fake' ? 'warn' : redis === 'down' ? 'err' : 'off'} />
            <span className="text-fg-muted">redis</span>
            <span className="ml-auto text-fg-dim">{redis ?? '—'}</span>
          </div>
        </div>
      </aside>
    </>
  )
}
