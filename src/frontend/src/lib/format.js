// Latency arrives in milliseconds; pick the unit that keeps 3 significant digits.
export function fmtLatency(ms) {
  if (ms == null || Number.isNaN(ms)) return '—'
  if (ms >= 1000) return `${(ms / 1000).toFixed(2)} s`
  if (ms >= 1) return `${ms.toFixed(ms >= 100 ? 0 : 2)} ms`
  const us = ms * 1000
  if (us >= 1) return `${us.toFixed(us >= 100 ? 0 : 1)} µs`
  return `${Math.round(us * 1000)} ns`
}

export function fmtPct(ratio, digits = 1) {
  if (ratio == null) return '—'
  return `${(ratio * 100).toFixed(digits)}%`
}

export function fmtSignedPct(ratio, digits = 2) {
  if (ratio == null) return '—'
  return `${ratio >= 0 ? '+' : ''}${(ratio * 100).toFixed(digits)}%`
}

export function fmtBytes(n) {
  if (n == null) return '—'
  const units = ['B', 'KB', 'MB', 'GB']
  let i = 0
  while (n >= 1024 && i < units.length - 1) {
    n /= 1024
    i++
  }
  return `${n.toFixed(i ? 1 : 0)} ${units[i]}`
}

const usd = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 })
export const fmtUsd = (n) => (n == null ? '—' : usd.format(n))

const compact = new Intl.NumberFormat('en-US', { notation: 'compact', maximumFractionDigits: 1 })
export const fmtCompact = (n) => (n == null ? '—' : compact.format(n))

export const fmtInt = (n) => (n == null ? '—' : n.toLocaleString('en-US'))

export function fmtClock(ts) {
  const d = new Date(ts * 1000)
  return `${d.toLocaleTimeString('en-GB', { hour12: false })}.${String(d.getMilliseconds()).padStart(3, '0')}`
}

export const cx = (...classes) => classes.filter(Boolean).join(' ')
