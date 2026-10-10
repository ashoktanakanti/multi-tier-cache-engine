import { cx } from '../lib/format'

export function Panel({ className, children }) {
  return <section className={cx('border border-line bg-ink-900 rounded-md min-w-0', className)}>{children}</section>
}

export function PanelHeader({ title, icon: Icon, meta, children }) {
  return (
    <header className="flex items-center gap-2 h-10 px-3 border-b border-line">
      {Icon && <Icon size={14} className="text-fg-dim shrink-0" strokeWidth={1.75} />}
      <h2 className="text-[13px] font-semibold tracking-tight truncate">{title}</h2>
      {meta && <span className="text-[11px] text-fg-dim font-mono truncate">{meta}</span>}
      <div className="ml-auto flex items-center gap-1.5">{children}</div>
    </header>
  )
}

export function SectionLabel({ children }) {
  return <div className="px-3 pt-4 pb-1.5 text-[10px] font-medium uppercase tracking-[0.12em] text-fg-faint">{children}</div>
}

const BUTTON_VARIANTS = {
  primary: 'bg-accent text-ink-950 hover:bg-amber-400 border-accent font-semibold',
  ghost: 'border-line text-fg-muted hover:text-fg hover:bg-ink-800',
  subtle: 'border-transparent text-fg-dim hover:text-fg hover:bg-ink-800',
}

export function Button({ variant = 'ghost', size = 'md', className, icon: Icon, children, ...props }) {
  return (
    <button
      className={cx(
        'inline-flex items-center justify-center gap-1.5 rounded border transition-colors disabled:opacity-40 disabled:pointer-events-none whitespace-nowrap',
        size === 'sm' ? 'h-6 px-2 text-[11px]' : 'h-8 px-3 text-[12px]',
        BUTTON_VARIANTS[variant],
        className,
      )}
      {...props}
    >
      {Icon && <Icon size={size === 'sm' ? 12 : 14} strokeWidth={2} />}
      {children}
    </button>
  )
}

export function Chip({ active, onClick, children, className }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cx(
        'h-6 px-2.5 rounded text-[11px] font-medium border transition-colors',
        active ? 'bg-accent text-ink-950 border-accent' : 'border-line text-fg-muted hover:text-fg hover:bg-ink-800',
        className,
      )}
    >
      {children}
    </button>
  )
}

export function Field({ label, children, className }) {
  return (
    <label className={cx('flex flex-col gap-1 min-w-0', className)}>
      <span className="text-[10px] uppercase tracking-[0.1em] text-fg-faint">{label}</span>
      {children}
    </label>
  )
}

export const inputClass =
  'h-8 w-full rounded border border-line bg-ink-850 px-2.5 font-mono text-[12px] text-fg placeholder:text-fg-faint focus:border-accent/60 focus:outline-none'

export function Input(props) {
  return <input {...props} className={cx(inputClass, props.className)} />
}

/** Thin horizontal capacity / share bar. */
export function Meter({ value, max = 1, tone = 'accent', className }) {
  const pct = max ? Math.min(100, Math.max(0, (value / max) * 100)) : 0
  return (
    <div className={cx('h-1 w-full rounded-full bg-ink-800 overflow-hidden', className)}>
      <div
        className={cx('h-full rounded-full transition-[width] duration-500', tone === 'accent' ? 'bg-accent' : 'bg-fg-dim')}
        style={{ width: `${pct}%` }}
      />
    </div>
  )
}

export function Dot({ tone }) {
  const color = { ok: 'bg-up', warn: 'bg-accent', off: 'bg-fg-faint', err: 'bg-down' }[tone]
  return <span className={cx('inline-block size-1.5 rounded-full shrink-0', color)} />
}

export function Kbd({ children }) {
  return (
    <kbd className="font-mono text-[10px] text-fg-dim border border-line rounded px-1 h-4 inline-flex items-center">
      {children}
    </kbd>
  )
}

export function Stat({ label, value, sub, accent }) {
  return (
    <div className="px-3 py-2.5 min-w-0">
      <div className="text-[10px] uppercase tracking-[0.1em] text-fg-faint truncate">{label}</div>
      <div className={cx('font-mono text-[17px] leading-6 mt-0.5 truncate', accent ? 'text-accent' : 'text-fg')}>{value}</div>
      {sub && <div className="font-mono text-[10.5px] text-fg-dim truncate">{sub}</div>}
    </div>
  )
}

export function ErrorNote({ error }) {
  if (!error) return null
  return (
    <div className="font-mono text-[11px] text-down border border-down/30 bg-down/5 rounded px-2.5 py-1.5">
      ERR {error.status ? `${error.status} ` : ''}— {error.message}
    </div>
  )
}

/** Which tier answered: L1 / L2 (cache hits, highlighted) or the database. */
export function TierTag({ source }) {
  const s = (source || '').toLowerCase()
  const hit = s === 'l1' || s === 'l2'
  return (
    <span
      className={cx(
        'font-mono text-[10px] px-1.5 h-[18px] inline-flex items-center rounded border uppercase tracking-wide',
        hit ? 'border-accent/40 text-accent bg-accent/10' : 'border-line text-fg-muted',
      )}
    >
      {s || '—'}
    </span>
  )
}
