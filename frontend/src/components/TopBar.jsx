import { useEffect, useRef, useState } from 'react'
import { Menu, Search } from 'lucide-react'
import { Kbd } from './ui'

/** Header with a global "read key" box: type an account id, press Enter to trace a lookup. */
export default function TopBar({ title, subtitle, onRead, onMenu }) {
  const [value, setValue] = useState('')
  const inputRef = useRef(null)

  useEffect(() => {
    const onKey = (e) => {
      if (e.key === '/' && document.activeElement?.tagName !== 'INPUT') {
        e.preventDefault()
        inputRef.current?.focus()
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  const submit = (e) => {
    e.preventDefault()
    const id = parseInt(value.replace(/\D/g, ''), 10)
    if (id > 0) {
      onRead(id)
      setValue('')
      inputRef.current?.blur()
    }
  }

  return (
    <header className="h-12 shrink-0 flex items-center gap-3 px-3 sm:px-4 border-b border-line bg-ink-950">
      <button className="lg:hidden text-fg-muted hover:text-fg" onClick={onMenu} aria-label="Open menu">
        <Menu size={18} />
      </button>
      <div className="min-w-0">
        <h1 className="text-[15px] font-semibold tracking-tight leading-5 truncate">{title}</h1>
        {subtitle && <p className="text-[11px] text-fg-dim leading-4 truncate hidden sm:block">{subtitle}</p>}
      </div>

      <form onSubmit={submit} className="ml-auto w-full max-w-[300px]">
        <div className="relative">
          <Search size={13} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-fg-faint" />
          <input
            ref={inputRef}
            value={value}
            onChange={(e) => setValue(e.target.value)}
            placeholder="Read portfolio:summary:<id>"
            inputMode="numeric"
            className="h-8 w-full rounded border border-line bg-ink-900 pl-8 pr-8 font-mono text-[12px] placeholder:text-fg-faint focus:border-accent/60 focus:outline-none"
          />
          <span className="absolute right-2 top-1/2 -translate-y-1/2 hidden sm:block"><Kbd>/</Kbd></span>
        </div>
      </form>
    </header>
  )
}
