import { useEffect, useState } from 'react'

import { Pagination } from '@/components/Pagination'
import { StatusBadge } from '@/components/StatusBadge'
import { useShipmentEvents } from '@/hooks/useShipments'
import { formatAbsolute, formatRelative } from '@/lib/format'
import { stateOf } from '@/lib/lifecycle'
import type { Lifecycle, Shipment } from '@/types/api'

interface Props {
  shipment: Shipment | null
  lifecycle: Lifecycle | undefined
  onClose: () => void
}

const PAGE_SIZE = 8

/** Paginated status history — the audit trail behind every status change. */
export function HistoryDrawer({ shipment, lifecycle, onClose }: Props) {
  const [page, setPage] = useState(1)
  const { data, isPending, isError, error } = useShipmentEvents(
    shipment?.id ?? null,
    page,
    PAGE_SIZE,
  )

  useEffect(() => setPage(1), [shipment?.id])

  useEffect(() => {
    if (!shipment) return
    const onEscape = (event: KeyboardEvent) => event.key === 'Escape' && onClose()
    document.addEventListener('keydown', onEscape)
    return () => document.removeEventListener('keydown', onEscape)
  }, [shipment, onClose])

  if (!shipment) return null

  return (
    <div
      className="fixed inset-0 z-30 flex justify-end bg-slate-900/30"
      onMouseDown={(event) => event.target === event.currentTarget && onClose()}
    >
      <aside
        className="flex h-full w-full max-w-lg flex-col bg-white shadow-2xl"
        role="dialog"
        aria-modal="true"
        aria-label={`Status history for ${shipment.reference}`}
      >
        <header className="flex items-start justify-between border-b border-slate-200 px-5 py-4">
          <div>
            <p className="text-xs font-medium uppercase tracking-wide text-slate-500">
              Status history
            </p>
            <h2 className="mt-0.5 text-lg font-semibold text-slate-900">{shipment.reference}</h2>
            <p className="text-sm text-slate-600">{shipment.customer_name}</p>
          </div>
          <button type="button" className="btn-ghost" onClick={onClose} aria-label="Close history">
            ✕
          </button>
        </header>

        <div className="flex-1 overflow-y-auto px-5 py-4">
          {isPending && <p className="text-sm text-slate-500">Loading history…</p>}
          {isError && (
            <p className="text-sm text-rose-600">{(error as Error)?.message ?? 'Failed to load.'}</p>
          )}

          {data && (
            <ol className="relative space-y-5 border-l border-slate-200 pl-5">
              {data.items.map((event) => {
                const target = stateOf(lifecycle, event.target_status)
                const source = event.source_status ? stateOf(lifecycle, event.source_status) : null
                return (
                  <li key={event.id} className="relative">
                    <span className="absolute -left-[26px] top-1.5 h-2.5 w-2.5 rounded-full border-2 border-white bg-slate-300 ring-1 ring-slate-200" />
                    <div className="flex flex-wrap items-center gap-2">
                      {source && (
                        <>
                          <StatusBadge state={source} size="sm" />
                          <span className="text-slate-400" aria-hidden>
                            →
                          </span>
                        </>
                      )}
                      <StatusBadge state={target} size="sm" />
                    </div>
                    <p className="mt-1.5 text-xs text-slate-500" title={formatAbsolute(event.occurred_at)}>
                      {formatRelative(event.occurred_at)} · {event.actor} ·{' '}
                      <code className="text-slate-400">{event.event}</code>
                    </p>
                    {event.reason && (
                      <p className="mt-1.5 rounded-lg bg-slate-50 px-3 py-2 text-sm text-slate-700">
                        {event.reason}
                      </p>
                    )}
                  </li>
                )
              })}
            </ol>
          )}
        </div>

        {data && <Pagination meta={data.meta} onPageChange={setPage} label="events" />}
      </aside>
    </div>
  )
}
