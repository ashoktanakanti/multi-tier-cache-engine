import { useCallback, useEffect, useState } from 'react'
import { Play, RotateCw } from 'lucide-react'
import { api } from '../../lib/api'
import { cx, fmtLatency, fmtSignedPct, fmtUsd } from '../../lib/format'
import { Button, ErrorNote, Field, Input, TierTag } from '../ui'
import TraceSteps from './TraceSteps'

const EXPLAIN = {
  l1: 'L1 hit: answered from memory inside the API process. No network, no SQL.',
  l2: 'L1 missed, Redis had it. The value was also copied into L1 for next time.',
  db: 'Every cache tier missed, so the summary was computed with SQL and stored in the caches.',
}

function SummaryCard({ s }) {
  const perf = s.performance ?? {}
  const up = (n) => (n >= 0 ? 'text-up' : 'text-down')
  return (
    <div className="border border-line rounded">
      <div className="px-2.5 py-2 border-b border-line">
        <div className="text-[12px] font-semibold truncate">{s.account.account_name}</div>
        <div className="text-[11px] text-fg-dim truncate">{s.account.client_name} · prices as of {s.as_of}</div>
      </div>
      <div className="grid grid-cols-2 sm:grid-cols-4 divide-x divide-line border-b border-line font-mono">
        {[
          ['Market value', fmtUsd(s.market_value)],
          ['Profit / loss', <span key="pl" className={up(s.profit_loss)}>{fmtSignedPct(s.profit_loss_pct)}</span>],
          ['1Y return', <span key="r" className={up(perf.return_1y)}>{fmtSignedPct(perf.return_1y)}</span>],
          ['Volatility', perf.volatility != null ? `${(perf.volatility * 100).toFixed(1)}%` : '—'],
        ].map(([k, v]) => (
          <div key={k} className="px-2.5 py-1.5 min-w-0">
            <div className="text-[9.5px] uppercase tracking-[0.1em] text-fg-faint font-sans">{k}</div>
            <div className="text-[12.5px] truncate">{v}</div>
          </div>
        ))}
      </div>
      <table className="w-full font-mono text-[11px]">
        <tbody className="divide-y divide-line">
          {s.top_holdings.map((h) => (
            <tr key={h.ticker}>
              <td className="px-2.5 h-6">{h.ticker}</td>
              <td className="px-2 text-fg-dim truncate max-w-0 w-full hidden sm:table-cell font-sans">{h.sector}</td>
              <td className="px-2 text-right">{fmtUsd(h.market_value)}</td>
              <td className={cx('px-2.5 text-right', up(h.profit_loss))}>
                {h.profit_loss >= 0 ? '+' : ''}{fmtUsd(h.profit_loss)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export default function ReadTab({ request, onResult }) {
  const [accountId, setAccountId] = useState('1')
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)
  const [runId, setRunId] = useState(0)

  const run = useCallback(async (id) => {
    setBusy(true)
    setError(null)
    try {
      const r = await api.lookup(id)
      setResult(r)
      setRunId((n) => n + 1)
      onResult?.(r)
    } catch (err) {
      setError(err)
      setResult(null)
    } finally {
      setBusy(false)
    }
  }, [onResult])

  // Reads triggered from elsewhere (top bar search, accounts table, write tab)
  useEffect(() => {
    if (request?.id) {
      setAccountId(String(request.id))
      run(request.id)
    }
  }, [request, run])

  const submit = (e) => {
    e.preventDefault()
    const id = parseInt(accountId, 10)
    if (id > 0) run(id)
  }

  return (
    <div className="space-y-3">
      <form onSubmit={submit} className="flex items-end gap-2">
        <Field label="Account id" className="w-28">
          <Input value={accountId} onChange={(e) => setAccountId(e.target.value)} inputMode="numeric" />
        </Field>
        <div className="flex-1 min-w-0 pb-2 font-mono text-[11px] text-fg-dim truncate">
          key <span className="text-fg-muted">portfolio:summary:{accountId || '…'}</span>
        </div>
        <Button variant="primary" icon={Play} disabled={busy}>Read key</Button>
      </form>

      <ErrorNote error={error} />

      {result ? (
        <>
          <div className="flex items-center gap-2 flex-wrap">
            <TierTag source={result.source === 'db' ? 'L3 · DB' : result.source} />
            <span className="font-mono text-[12px]">{fmtLatency(result.total_ms)}</span>
            <span className="text-[11px] text-fg-dim">total on the server</span>
            <Button size="sm" icon={RotateCw} className="ml-auto" disabled={busy}
              onClick={() => run(parseInt(accountId, 10))}>Read again</Button>
          </div>
          <p className="text-[11.5px] text-fg-muted">{EXPLAIN[result.source]}</p>
          <TraceSteps steps={result.steps} runId={runId} />
          <SummaryCard s={result.summary} />
        </>
      ) : (
        !error && (
          <p className="text-[11.5px] text-fg-dim leading-5">
            Reads one account summary through the real cache and shows every tier it checked, with measured times.
            Try a new account, then press <span className="text-fg-muted">Read again</span>: the second read comes from L1.
          </p>
        )
      )}
    </div>
  )
}
