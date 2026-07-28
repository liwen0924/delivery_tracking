import { useEffect, useRef, useState } from 'react'

import type { Lifecycle, Shipment, TransitionOption } from '@/types/api'
import { stateOf, statusDot } from '@/lib/lifecycle'

interface Props {
  shipment: Shipment
  lifecycle: Lifecycle | undefined
  busy: boolean
  onSelect: (option: TransitionOption) => void
}

/**
 * Offers only the transitions the server said are legal for this shipment, so
 * the UI cannot even ask for an invalid move. The server still validates —
 * this is convenience, not the rule.
 */
export function TransitionMenu({ shipment, lifecycle, busy, onSelect }: Props) {
  const [open, setOpen] = useState(false)
  const containerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    const close = (event: MouseEvent) => {
      if (!containerRef.current?.contains(event.target as Node)) setOpen(false)
    }
    const onEscape = (event: KeyboardEvent) => event.key === 'Escape' && setOpen(false)
    document.addEventListener('mousedown', close)
    document.addEventListener('keydown', onEscape)
    return () => {
      document.removeEventListener('mousedown', close)
      document.removeEventListener('keydown', onEscape)
    }
  }, [open])

  if (shipment.allowed_transitions.length === 0) {
    return (
      <span className="text-xs text-slate-400" title="This status is terminal.">
        No further actions
      </span>
    )
  }

  return (
    <div className="relative inline-block text-left" ref={containerRef}>
      <button
        type="button"
        className="btn-secondary"
        onClick={() => setOpen((value) => !value)}
        disabled={busy}
        aria-haspopup="menu"
        aria-expanded={open}
      >
        {busy ? 'Updating…' : 'Update status'}
        <span className="text-slate-400" aria-hidden>
          ▾
        </span>
      </button>

      {open && (
        <div
          role="menu"
          className="animate-fade-in-up absolute right-0 z-20 mt-1 w-64 overflow-hidden rounded-xl border border-slate-200 bg-white py-1 shadow-lg"
        >
          {shipment.allowed_transitions.map((option) => {
            const target = stateOf(lifecycle, option.target)
            return (
              <button
                key={option.target}
                type="button"
                role="menuitem"
                className="flex w-full items-start gap-2.5 px-3 py-2 text-left hover:bg-slate-50"
                onClick={() => {
                  setOpen(false)
                  onSelect(option)
                }}
              >
                <span
                  className={`mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full ${statusDot(target.tone)}`}
                  aria-hidden
                />
                <span className="min-w-0">
                  <span className="block text-sm font-medium text-slate-800">{option.label}</span>
                  <span className="block text-xs text-slate-500">
                    {option.requires_reason ? 'Requires a reason' : target.description}
                  </span>
                </span>
              </button>
            )
          })}
        </div>
      )}
    </div>
  )
}
