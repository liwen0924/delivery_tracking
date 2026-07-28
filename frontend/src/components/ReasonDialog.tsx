import { useEffect, useRef, useState } from 'react'

import type { Shipment, TransitionOption } from '@/types/api'

interface Props {
  shipment: Shipment
  option: TransitionOption
  submitting: boolean
  onCancel: () => void
  onConfirm: (reason: string) => void
}

/**
 * Shown when the chosen transition declares the `require_reason` guard in the
 * lifecycle config. The guard is enforced server-side regardless.
 */
export function ReasonDialog({ shipment, option, submitting, onCancel, onConfirm }: Props) {
  const [reason, setReason] = useState('')
  const inputRef = useRef<HTMLTextAreaElement>(null)

  useEffect(() => {
    inputRef.current?.focus()
    const onEscape = (event: KeyboardEvent) => event.key === 'Escape' && onCancel()
    document.addEventListener('keydown', onEscape)
    return () => document.removeEventListener('keydown', onEscape)
  }, [onCancel])

  const valid = reason.trim().length > 0

  return (
    <div
      className="fixed inset-0 z-40 flex items-center justify-center bg-slate-900/30 p-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="reason-dialog-title"
      onMouseDown={(event) => event.target === event.currentTarget && onCancel()}
    >
      <form
        className="animate-fade-in-up card w-full max-w-md p-5"
        onSubmit={(event) => {
          event.preventDefault()
          if (valid) onConfirm(reason.trim())
        }}
      >
        <h2 id="reason-dialog-title" className="text-base font-semibold text-slate-900">
          {option.label}
        </h2>
        <p className="mt-1 text-sm text-slate-600">
          {shipment.reference} · {shipment.customer_name}
        </p>

        <label className="mt-4 block text-sm font-medium text-slate-700" htmlFor="reason">
          Reason <span className="text-rose-600">*</span>
        </label>
        <textarea
          id="reason"
          ref={inputRef}
          className="field mt-1 min-h-24 resize-y"
          maxLength={500}
          placeholder="e.g. Recipient not at address, redelivery declined"
          value={reason}
          onChange={(event) => setReason(event.target.value)}
        />
        <p className="mt-1 text-xs text-slate-500">
          Stored on the status history so the failure stays auditable.
        </p>

        <div className="mt-5 flex justify-end gap-2">
          <button type="button" className="btn-secondary" onClick={onCancel} disabled={submitting}>
            Cancel
          </button>
          <button type="submit" className="btn-primary" disabled={!valid || submitting}>
            {submitting ? 'Saving…' : 'Confirm'}
          </button>
        </div>
      </form>
    </div>
  )
}
