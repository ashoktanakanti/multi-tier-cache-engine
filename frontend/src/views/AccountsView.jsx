import { useEffect, useMemo, useState } from 'react'
import { ArrowRight, ChevronLeft, ChevronRight, ListTree, RefreshCw, Search } from 'lucide-react'
import { api } from '../lib/api'
import { cx, fmtInt } from '../lib/format'
import { Button, Chip, ErrorNote, Panel, PanelHeader } from '../components/ui'

const PAGE = 50

export default function AccountsView({ onTrace }) {
  const [offset, setOffset] = useState(0)
  const [rows, setRows] = useState([])
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(true)
  const [query, setQuery] = useState('')
  const [filter, setFilter] = useState('all')
  const [nonce, setNonce] = useState(0)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    api.accounts(PAGE, offset)
      .then((r) => { if (!cancelled) { setRows(r); setError(null) } })
      .catch((err) => !cancelled && setError(err))
      .finally(() => !cancelled && setLoading(false))
    return () => { cancelled = true }
  }, [offset, nonce])

  const visible = useMemo(() => {
    const q = query.trim().toLowerCase()
    return rows.filter((r) =>
      (filter === 'all' || (filter === 'cached') === r.cached) &&
      (!q || `${r.account_id} ${r.account_name} ${r.client_name}`.toLowerCase().includes(q)))
  }, [rows, query, filter])

  const cachedCount = rows.filter((r) => r.cached).length

  return (
    <Panel>
      <PanelHeader title="Client accounts" icon={ListTree} meta="GET /accounts · cheap query, not cached">
        <Button size="sm" variant="ghost" icon={RefreshCw} onClick={() => setNonce((n) => n + 1)}>Refresh</Button>
      </PanelHeader>

      <div className="flex flex-wrap items-center gap-2 px-3 py-2 border-b border-line">
        <div className="flex gap-1">
          <Chip active={filter === 'all'} onClick={() => setFilter('all')}>All</Chip>
          <Chip active={filter === 'cached'} onClick={() => setFilter('cached')}>In L1 · {cachedCount}</Chip>
          <Chip active={filter === 'cold'} onClick={() => setFilter('cold')}>Not cached · {rows.length - cachedCount}</Chip>
        </div>
        <div className="relative ml-auto w-full sm:w-64">
          <Search size={13} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-fg-faint" />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Filter this page"
            className="h-7 w-full rounded border border-line bg-ink-850 pl-8 pr-2 text-[12px] placeholder:text-fg-faint focus:border-accent/60 focus:outline-none"
          />
        </div>
      </div>

      <ErrorNote error={error} />

      <div className="overflow-x-auto">
        <table className="w-full text-[12px] min-w-[640px]">
          <thead>
            <tr className="border-b border-line text-[10.5px] uppercase tracking-[0.08em] text-fg-faint">
              <th className="text-left font-medium px-3 h-8 w-14">#</th>
              <th className="text-left font-medium px-2">Account</th>
              <th className="text-left font-medium px-2">Client</th>
              <th className="text-right font-medium px-2 w-24">Positions</th>
              <th className="text-left font-medium px-2 w-28">Cache state</th>
              <th className="w-24" />
            </tr>
          </thead>
          <tbody className={cx('divide-y divide-line', loading && 'opacity-60')}>
            {visible.map((r) => (
              <tr key={r.account_id} className="group hover:bg-ink-850">
                <td className="px-3 h-9 font-mono text-fg-dim">{r.account_id}</td>
                <td className="px-2 font-medium truncate max-w-[260px]">{r.account_name}</td>
                <td className="px-2 text-fg-muted truncate max-w-[220px]">{r.client_name}</td>
                <td className="px-2 text-right font-mono">{r.positions}</td>
                <td className="px-2">
                  <span className={cx('inline-flex items-center gap-1.5 font-mono text-[11px]', r.cached ? 'text-accent' : 'text-fg-faint')}>
                    <span className={cx('size-1.5 rounded-full', r.cached ? 'bg-accent' : 'bg-fg-faint')} />
                    {r.cached ? 'in L1' : 'not cached'}
                  </span>
                </td>
                <td className="px-3 text-right">
                  <Button size="sm" variant="ghost" icon={ArrowRight} onClick={() => onTrace(r.account_id)}
                    className="opacity-70 group-hover:opacity-100">Trace</Button>
                </td>
              </tr>
            ))}
            {!loading && visible.length === 0 && (
              <tr><td colSpan={6} className="px-3 h-16 text-center text-fg-dim">No accounts match.</td></tr>
            )}
          </tbody>
        </table>
      </div>

      <footer className="flex items-center gap-2 px-3 h-10 border-t border-line font-mono text-[11px] text-fg-dim">
        <span>{fmtInt(offset + 1)}–{fmtInt(offset + rows.length)}</span>
        <span className="text-fg-faint">· {visible.length} shown</span>
        <div className="ml-auto flex gap-1">
          <Button size="sm" variant="ghost" icon={ChevronLeft} disabled={offset === 0} onClick={() => setOffset((o) => Math.max(0, o - PAGE))}>Prev</Button>
          <Button size="sm" variant="ghost" disabled={rows.length < PAGE} onClick={() => setOffset((o) => o + PAGE)}>
            Next <ChevronRight size={12} />
          </Button>
        </div>
      </footer>
    </Panel>
  )
}
