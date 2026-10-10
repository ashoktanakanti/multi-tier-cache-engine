import { useState } from 'react'
import { FlaskConical } from 'lucide-react'
import { cx } from '../../lib/format'
import { Panel, PanelHeader } from '../ui'
import LoadTab from './LoadTab'
import PriceTab from './PriceTab'
import ReadTab from './ReadTab'
import WriteTab from './WriteTab'

const TABS = [
  { id: 'read', label: 'READ KEY', hint: 'L1 → L2 → L3' },
  { id: 'write', label: 'WRITE', hint: 'trade → invalidate' },
  { id: 'price', label: 'PRICE', hint: 'update → invalidate holders' },
  { id: 'load', label: 'STATS', hint: 'generate traffic' },
]

export default function SimulatorPanel({ readRequest, onReadResult, onTraceRead, lastPreview, redis, onReset }) {
  const [tab, setTab] = useState('read')

  // Switch to READ whenever an external read is requested (top bar, accounts table).
  const [seenRequest, setSeenRequest] = useState(readRequest)
  if (readRequest !== seenRequest) {
    setSeenRequest(readRequest)
    if (tab !== 'read') setTab('read')
  }
  const active = tab

  return (
    <Panel className="flex flex-col">
      <PanelHeader title="Playground" icon={FlaskConical} meta="live engine · real timings" />
      <div className="flex border-b border-line overflow-x-auto" role="tablist">
        {TABS.map((t) => (
          <button
            key={t.id}
            role="tab"
            aria-selected={active === t.id}
            onClick={() => setTab(t.id)}
            className={cx(
              'flex-1 min-w-[84px] h-10 px-3 text-left border-r border-line last:border-r-0 transition-colors',
              active === t.id ? 'bg-ink-850 shadow-[inset_0_-2px_0_var(--color-accent)]' : 'hover:bg-ink-800',
            )}
          >
            <div className={cx('font-mono text-[11.5px] font-semibold', active === t.id ? 'text-accent' : 'text-fg-muted')}>{t.label}</div>
            <div className="text-[10px] text-fg-faint truncate">{t.hint}</div>
          </button>
        ))}
      </div>
      <div className="p-3 flex-1">
        {/* Keep tabs mounted so their state survives switching. */}
        <div hidden={active !== 'read'}><ReadTab request={readRequest} onResult={onReadResult} /></div>
        <div hidden={active !== 'write'}><WriteTab lastPreview={lastPreview} redis={redis} onTraceRead={onTraceRead} /></div>
        <div hidden={active !== 'price'}><PriceTab /></div>
        <div hidden={active !== 'load'}><LoadTab onReset={onReset} /></div>
      </div>
    </Panel>
  )
}
