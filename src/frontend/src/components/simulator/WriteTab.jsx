import { useEffect, useState } from 'react'
import { ArrowRight, Send } from 'lucide-react'
import { api } from '../../lib/api'
import { Button, Chip, ErrorNote, Field, Input } from '../ui'
import TickerInput from './TickerInput'
import WritePath from './WritePath'

export default function WriteTab({ lastPreview, redis, onTraceRead }) {
  const [accountId, setAccountId] = useState('1')
  const [ticker, setTicker] = useState('')
  const [side, setSide] = useState('BUY')
  const [quantity, setQuantity] = useState('100')
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)
  const [runId, setRunId] = useState(0)

  // Default to the account (and its largest holding) from the last READ.
  useEffect(() => {
    if (lastPreview) {
      setAccountId(String(lastPreview.account.account_id))
      setTicker(lastPreview.top_holdings[0]?.ticker ?? '')
    }
  }, [lastPreview])

  const holdings = lastPreview?.account.account_id === Number(accountId) ? lastPreview.top_holdings : []

  const submit = async (e) => {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      const r = await api.trade(Number(accountId), { ticker, side, quantity: Number(quantity) })
      setResult(r)
      setRunId((n) => n + 1)
    } catch (err) {
      setError(err)
      setResult(null)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="space-y-3">
      <form onSubmit={submit} className="grid grid-cols-2 sm:grid-cols-[90px_minmax(0,1fr)_auto_90px] gap-2 items-end">
        <Field label="Account">
          <Input value={accountId} onChange={(e) => setAccountId(e.target.value)} inputMode="numeric" />
        </Field>
        <Field label="Ticker">
          <TickerInput value={ticker} onChange={setTicker}
            suggestions={holdings.map((h) => ({ ticker: h.ticker, sector: h.sector, last_close: h.last_close }))} />
        </Field>
        <Field label="Side">
          <div className="flex gap-1 h-8 items-center">
            {['BUY', 'SELL'].map((s) => (
              <Chip key={s} active={side === s} onClick={() => setSide(s)}>{s}</Chip>
            ))}
          </div>
        </Field>
        <Field label="Quantity">
          <Input value={quantity} onChange={(e) => setQuantity(e.target.value)} inputMode="decimal" />
        </Field>
        <Button variant="primary" icon={Send} disabled={busy || !ticker} className="col-span-2 sm:col-span-4">
          Execute trade &amp; invalidate
        </Button>
      </form>

      <ErrorNote error={error} />

      {result ? (
        <>
          <div className="font-mono text-[11.5px] text-fg-muted">
            trade #{result.trade_id} · {result.side} {result.quantity} {result.ticker} @ {result.price.toFixed(2)}
          </div>
          <WritePath result={result} redis={redis} runId={runId} />
          <div className="flex items-center gap-2">
            <p className="text-[11.5px] text-fg-dim flex-1">
              Invalidated <span className="font-mono text-fg-muted">{result.invalidated.join(', ')}</span>. We delete the cached
              copy instead of updating it, so the next read reloads fresh data from the database.
            </p>
            <Button size="sm" icon={ArrowRight} onClick={() => onTraceRead(result.account_id)}>Trace next read</Button>
          </div>
        </>
      ) : (
        !error && (
          <p className="text-[11.5px] text-fg-dim leading-5">
            Runs a real trade in one SQL transaction, then deletes only that account&rsquo;s cached summary.
            Selling more than the account holds is rejected.
          </p>
        )
      )}
    </div>
  )
}
