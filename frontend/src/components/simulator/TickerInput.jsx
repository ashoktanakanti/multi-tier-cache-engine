import { useEffect, useState } from 'react'
import { api } from '../../lib/api'
import { fmtUsd } from '../../lib/format'
import { inputClass } from '../ui'

/** Ticker box with debounced prefix search against /securities. */
export default function TickerInput({ value, onChange, onPick, suggestions: preset = [] }) {
  const [results, setResults] = useState([])
  const [open, setOpen] = useState(false)

  useEffect(() => {
    if (!open) return
    const q = value.trim()
    if (!q) {
      setResults(preset)
      return
    }
    const t = setTimeout(() => api.securities(q).then(setResults).catch(() => setResults([])), 150)
    return () => clearTimeout(t)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [value, open])

  return (
    <div className="relative">
      <input
        value={value}
        onChange={(e) => onChange(e.target.value.toUpperCase())}
        onFocus={() => setOpen(true)}
        onBlur={() => setTimeout(() => setOpen(false), 120)}
        placeholder="TICKER"
        className={inputClass}
        autoComplete="off"
      />
      {open && results.length > 0 && (
        <ul className="absolute z-20 mt-1 w-[260px] max-h-56 overflow-auto rounded border border-line-strong bg-ink-850 py-1 shadow-xl shadow-black/40">
          {results.map((s) => (
            <li key={s.ticker}>
              <button
                type="button"
                onMouseDown={() => { onChange(s.ticker); onPick?.(s); setOpen(false) }}
                className="w-full grid grid-cols-[48px_minmax(0,1fr)_auto] gap-2 px-2.5 h-7 items-center text-left hover:bg-ink-800"
              >
                <span className="font-mono text-[11.5px] text-fg">{s.ticker}</span>
                <span className="text-[11px] text-fg-dim truncate">{s.sector}</span>
                <span className="font-mono text-[11px] text-fg-muted">{s.last_close != null ? fmtUsd(s.last_close) : ''}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
