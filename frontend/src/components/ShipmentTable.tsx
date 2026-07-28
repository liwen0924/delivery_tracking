import { StatusBadge } from '@/components/StatusBadge'
import { TransitionMenu } from '@/components/TransitionMenu'
import { formatAbsolute, formatRelative } from '@/lib/format'
import { stateOf } from '@/lib/lifecycle'
import type { Lifecycle, Shipment, SortField, TransitionOption } from '@/types/api'

interface Props {
  shipments: Shipment[]
  lifecycle: Lifecycle | undefined
  sortBy: SortField
  sortDir: 'asc' | 'desc'
  onSort: (field: SortField) => void
  pendingId: string | null
  onTransition: (shipment: Shipment, option: TransitionOption) => void
  onShowHistory: (shipment: Shipment) => void
  isRefreshing: boolean
}

const COLUMNS: { key: SortField | null; label: string; className?: string }[] = [
  { key: 'reference', label: 'Reference' },
  { key: 'customer_name', label: 'Customer' },
  { key: 'status', label: 'Status' },
  { key: 'status_changed_at', label: 'Last update' },
  { key: null, label: '', className: 'text-right' },
]

export function ShipmentTable({
  shipments,
  lifecycle,
  sortBy,
  sortDir,
  onSort,
  pendingId,
  onTransition,
  onShowHistory,
  isRefreshing,
}: Props) {
  return (
    <div className={`overflow-x-auto transition-opacity ${isRefreshing ? 'opacity-60' : ''}`}>
      <table className="w-full border-collapse text-left text-sm">
        <thead>
          <tr className="border-b border-slate-200 bg-slate-50/80">
            {COLUMNS.map((column) => (
              <th
                key={column.label || 'actions'}
                scope="col"
                className={`px-4 py-2.5 text-xs font-semibold uppercase tracking-wide text-slate-500 ${column.className ?? ''}`}
              >
                {column.key ? (
                  <button
                    type="button"
                    className="inline-flex items-center gap-1 hover:text-slate-800"
                    onClick={() => onSort(column.key as SortField)}
                  >
                    {column.label}
                    <span className="text-[10px]" aria-hidden>
                      {sortBy === column.key ? (sortDir === 'asc' ? '▲' : '▼') : '↕'}
                    </span>
                  </button>
                ) : (
                  <span className="sr-only">Actions</span>
                )}
              </th>
            ))}
          </tr>
        </thead>

        <tbody className="divide-y divide-slate-100">
          {shipments.map((shipment) => {
            const state = stateOf(lifecycle, shipment.status)
            return (
              <tr key={shipment.id} className="group hover:bg-slate-50/70">
                <td className="whitespace-nowrap px-4 py-3">
                  <button
                    type="button"
                    className="font-medium text-indigo-700 hover:underline"
                    onClick={() => onShowHistory(shipment)}
                    title="View status history"
                  >
                    {shipment.reference}
                  </button>
                </td>
                <td className="px-4 py-3 text-slate-700">{shipment.customer_name}</td>
                <td className="px-4 py-3">
                  <StatusBadge state={state} />
                  {shipment.last_event?.reason && state.tone === 'danger' && (
                    <p className="mt-1 max-w-[22ch] truncate text-xs text-slate-500" title={shipment.last_event.reason}>
                      {shipment.last_event.reason}
                    </p>
                  )}
                </td>
                <td
                  className="whitespace-nowrap px-4 py-3 text-slate-500"
                  title={formatAbsolute(shipment.status_changed_at)}
                >
                  {formatRelative(shipment.status_changed_at)}
                </td>
                <td className="whitespace-nowrap px-4 py-3 text-right">
                  <div className="inline-flex items-center gap-2">
                    <button
                      type="button"
                      className="btn-ghost opacity-0 transition-opacity focus:opacity-100 group-hover:opacity-100"
                      onClick={() => onShowHistory(shipment)}
                    >
                      History
                    </button>
                    <TransitionMenu
                      shipment={shipment}
                      lifecycle={lifecycle}
                      busy={pendingId === shipment.id}
                      onSelect={(option) => onTransition(shipment, option)}
                    />
                  </div>
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
