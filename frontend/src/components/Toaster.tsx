/** Minimal toast system — enough for success/error feedback, no dependency. */

import { createContext, use, useCallback, useMemo, useRef, useState } from 'react'
import type { ReactNode } from 'react'

type ToastTone = 'success' | 'error' | 'info'

interface Toast {
  id: number
  tone: ToastTone
  title: string
  description?: string
}

interface ToastContextValue {
  notify: (toast: Omit<Toast, 'id'>) => void
}

const ToastContext = createContext<ToastContextValue | null>(null)

const TONE_STYLES: Record<ToastTone, string> = {
  success: 'border-emerald-200 bg-white text-emerald-900',
  error: 'border-rose-200 bg-white text-rose-900',
  info: 'border-slate-200 bg-white text-slate-900',
}

const TONE_ICONS: Record<ToastTone, string> = {
  success: 'text-emerald-500',
  error: 'text-rose-500',
  info: 'text-slate-400',
}

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([])
  const nextId = useRef(1)

  const dismiss = useCallback((id: number) => {
    setToasts((current) => current.filter((toast) => toast.id !== id))
  }, [])

  const notify = useCallback(
    (toast: Omit<Toast, 'id'>) => {
      const id = nextId.current++
      setToasts((current) => [...current, { ...toast, id }])
      window.setTimeout(() => dismiss(id), toast.tone === 'error' ? 7000 : 4000)
    },
    [dismiss],
  )

  const value = useMemo(() => ({ notify }), [notify])

  return (
    <ToastContext value={value}>
      {children}
      <div
        className="pointer-events-none fixed bottom-4 right-4 z-50 flex w-full max-w-sm flex-col gap-2"
        role="status"
        aria-live="polite"
      >
        {toasts.map((toast) => (
          <div
            key={toast.id}
            className={`animate-fade-in-up pointer-events-auto flex items-start gap-3 rounded-xl border p-3 shadow-lg ${TONE_STYLES[toast.tone]}`}
          >
            <span className={`mt-0.5 text-lg leading-none ${TONE_ICONS[toast.tone]}`} aria-hidden>
              {toast.tone === 'success' ? '✓' : toast.tone === 'error' ? '!' : 'i'}
            </span>
            <div className="min-w-0 flex-1">
              <p className="text-sm font-semibold">{toast.title}</p>
              {toast.description && (
                <p className="mt-0.5 text-sm text-slate-600">{toast.description}</p>
              )}
            </div>
            <button
              type="button"
              onClick={() => dismiss(toast.id)}
              className="rounded p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-600"
              aria-label="Dismiss notification"
            >
              ✕
            </button>
          </div>
        ))}
      </div>
    </ToastContext>
  )
}

export function useToast(): ToastContextValue {
  const context = use(ToastContext)
  if (!context) throw new Error('useToast must be used inside <ToastProvider>')
  return context
}
