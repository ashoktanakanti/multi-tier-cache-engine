import { useCallback, useState } from 'react'
import MetricsBar from './components/MetricsBar'
import Sidebar from './components/Sidebar'
import SimulatorPanel from './components/simulator/SimulatorPanel'
import TerminalLog from './components/TerminalLog'
import TierVisualizer from './components/TierVisualizer'
import TopBar from './components/TopBar'
import { useEventStream } from './hooks/useEventStream'
import { usePolling } from './hooks/usePolling'
import { api } from './lib/api'
import AccountsView from './views/AccountsView'
import BenchmarkView from './views/BenchmarkView'
import DesignView from './views/DesignView'

const TITLES = {
  overview: ['Overview', 'L1 memory → L2 Redis → L3 database · cache-aside, delete on write'],
  accounts: ['Accounts', '500 client portfolios · click Trace to read one through the tiers'],
  benchmark: ['Benchmark', 'When the cache pays for itself, and when it doesn’t'],
  design: ['Design notes', 'Why cache this, and the trade-offs behind each choice'],
}

export default function App() {
  const [view, setView] = useState('overview')
  const [menuOpen, setMenuOpen] = useState(false)
  const [logOpen, setLogOpen] = useState(true)
  const [readRequest, setReadRequest] = useState(null)
  const [lastRead, setLastRead] = useState(null)

  const health = usePolling(api.health, 5000)
  const stats = usePolling(api.stats, 1000)
  const log = useEventStream(1000)
  const offline = health.error && stats.error

  const traceRead = useCallback((id) => {
    setReadRequest({ id, nonce: Date.now() })
    setView('overview')
  }, [])

  const { refresh: refreshStats } = stats
  const onReadResult = useCallback((r) => {
    setLastRead(r)
    setReadRequest(null) // consumed: don't replay it when the panel remounts
    refreshStats()
  }, [refreshStats])

  const [title, subtitle] = TITLES[view]

  return (
    <div className="h-full flex overflow-hidden">
      <Sidebar
        view={view}
        onNavigate={(v) => { setView(v); setMenuOpen(false) }}
        health={health.data}
        stats={stats.data}
        open={menuOpen}
        onClose={() => setMenuOpen(false)}
      />

      <div className="flex-1 min-w-0 flex flex-col">
        <TopBar title={title} subtitle={subtitle} onRead={traceRead} onMenu={() => setMenuOpen(true)} />

        {offline && (
          <div className="px-4 py-1.5 border-b border-down/30 bg-down/5 font-mono text-[11.5px] text-down">
            API unreachable. Start the backend: <span className="text-fg">uvicorn portfolio.api:app --port 8000</span>
          </div>
        )}

        <main className="flex-1 overflow-y-auto p-3 sm:p-4 space-y-3">
          {view === 'overview' && (
            <>
              <MetricsBar stats={stats.data} />
              <div className="grid gap-3 xl:grid-cols-[minmax(0,1.15fr)_minmax(0,1fr)] items-start">
                <TierVisualizer stats={stats.data} redis={health.data?.redis} flashTier={lastRead?.source} key={lastRead ? lastRead.key + lastRead.total_ms : 'idle'} />
                <SimulatorPanel
                  readRequest={readRequest}
                  onReadResult={onReadResult}
                  onTraceRead={traceRead}
                  lastPreview={lastRead?.summary}
                  redis={health.data?.redis}
                  onReset={() => { stats.refresh(); log.clear() }}
                />
              </div>
            </>
          )}
          {view === 'accounts' && <AccountsView onTrace={traceRead} />}
          {view === 'benchmark' && <BenchmarkView />}
          {view === 'design' && <DesignView />}
        </main>

        <TerminalLog {...log} open={logOpen} setOpen={setLogOpen} />
      </div>
    </div>
  )
}
