import { useState } from 'react'
import { Upload } from 'lucide-react'
import { api } from '../../lib/api'
import { fmtInt, fmtLatency, fmtUsd } from '../../lib/format'
import { Button, ErrorNote, Field, Input } from '../ui'
import TickerInput from './TickerInput'

export default function PriceTab() {
  const [ticker, setTicker] = useState('')
  const [lastClose, setLastClose] = useState(null)
  const [close, setClose] = useState('')
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)

  const submit = async (e) => {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      setResult(await api.updatePrice(ticker, Number(close)))
    } catch (err) {
      setError(err)
      setResult(null)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="space-y-3">
      <form onSubmit={submit} className="grid grid-cols-2 sm:grid-cols-[minmax(0,1fr)_120px_auto] gap-2 items-end">
        <Field label="Ticker">
          <TickerInput value={ticker} onChange={setTicker}
            onPick={(s) => { setLastClose(s.last_close); setClose((s.last_close * 1.02).toFixed(2)) }} />
        </Field>
        <Field label="New price">
          <Input value={close} onChange={(e) => setClose(e.target.value)} inputMode="decimal" />
        </Field>
        <Button variant="primary" icon={Upload} disabled={busy || !ticker || !close} className="col-span-2 sm:col-span-1">
          Update price
        </Button>
      </form>
      {lastClose != null && <div className="font-mono text-[11px] text-fg-dim">current price {fmtUsd(lastClose)}</div>}

      <ErrorNote error={error} />

      {result && (
        <div className="grid grid-cols-3 border border-line rounded divide-x divide-line font-mono animate-step-in">
          {[
            ['Accounts invalidated', fmtInt(result.accounts_invalidated)],
            ['DB update', fmtLatency(result.db_ms)],
            ['Invalidation', fmtLatency(result.invalidate_ms)],
          ].map(([k, v]) => (
            <div key={k} className="px-2.5 py-2 min-w-0">
              <div className="text-[9.5px] uppercase tracking-[0.1em] text-fg-faint font-sans truncate">{k}</div>
              <div className="text-[13px] text-accent truncate">{v}</div>
            </div>
          ))}
        </div>
      )}

      <p className="text-[11.5px] text-fg-dim leading-5">
        One price change affects every portfolio that holds that security, so the service finds all of those accounts
        and deletes each one&rsquo;s cached summary.
      </p>
    </div>
  )
}
