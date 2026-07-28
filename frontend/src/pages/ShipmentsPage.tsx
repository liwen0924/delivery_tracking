import { useEffect, useMemo, useState } from 'react'

import { ApiError } from '@/api/client'
import { HistoryDrawer } from '@/components/HistoryDrawer'
import { Pagination } from '@/components/Pagination'
import { ReasonDialog } from '@/components/ReasonDialog'
import { ShipmentTable } from '@/components/ShipmentTable'
import { StatusFilterBar } from '@/components/StatusFilterBar'
import { useToast } from '@/components/Toaster'
import { LifecycleRail } from '@/components/LifecycleRail'
import {
  useLifecycle,
  useShipments,
  useSummary,
  useUpdateStatus,
} from '@/hooks/useShipments'
import { useDebounced } from '@/hooks/useDebounced'
import { stateOf } from '@/lib/lifecycle'
import type { Shipment, ShipmentQuery, SortField, TransitionOption } from '@/types/api'

const DEFAULT_QUERY: ShipmentQuery = {
  page: 1,
  pageSize: 10,
  statuses: [],
  search: '',
  sortBy: 'reference',
  sortDir: 'asc',
}

export function ShipmentsPage() {
  const { notify } = useToast()

  const [searchInput, setSearchInput] = useState('')
  const search = useDebounced(searchInput, 300)
  const [query, setQuery] = useState<ShipmentQuery>(DEFAULT_QUERY)

  const [historyFor, setHistoryFor] = useState<Shipment | null>(null)
  const [pending, setPending] = useState<{ shipment: Shipment; option: TransitionOption } | null>(
    null,
  )

  // Any change to the filters invalidates the current page number.
  useEffect(() => {
    setQuery((current) => ({ ...current, search, page: 1 }))
  }, [search])

  const lifecycleQuery = useLifecycle()
  const summaryQuery = useSummary()
  const shipmentsQuery = useShipments(query)

  const updateStatus = useUpdateStatus((result) => {
    const to = stateOf(lifecycleQuery.data, result.shipment.status)
    notify({
      tone: 'success',
      title: `${result.shipment.reference} → ${to.label}`,
      description: result.event.reason ?? undefined,
    })
  })

  const applyTransition = (shipment: Shipment, option: TransitionOption, reason?: string) => {
    updateStatus.mutate(
      {
        shipmentId: shipment.id,
        status: option.target,
        reason,
        expectedVersion: shipment.version,
      },
      {
        onSuccess: () => setPending(null),
        onError: (error) => {
          const apiError = error as ApiError
          const allowed = apiError.allowedTargets
            .map((code) => stateOf(lifecycleQuery.data, code).label)
            .join(', ')
          notify({
            tone: 'error',
            title: `Could not update ${shipment.reference}`,
            description: allowed ? `${apiError.message} (allowed: ${allowed})` : apiError.message,
          })
          setPending(null)
        },
      },
    )
  }

  const onTransition = (shipment: Shipment, option: TransitionOption) => {
    if (option.requires_reason) {
      setPending({ shipment, option })
      return
    }
    setPending({ shipment, option })
    applyTransition(shipment, option)
  }

  const onSort = (field: SortField) => {
    setQuery((current) => ({
      ...current,
      sortBy: field,
      sortDir: current.sortBy === field && current.sortDir === 'asc' ? 'desc' : 'asc',
      page: 1,
    }))
  }

  const shipments = shipmentsQuery.data?.items ?? []
  const meta = shipmentsQuery.data?.meta
  const activeFilters = query.statuses.length > 0 || query.search.length > 0

  const pendingShipmentId = useMemo(
    () => (updateStatus.isPending ? (pending?.shipment.id ?? null) : null),
    [updateStatus.isPending, pending],
  )

  return (
    <div className="mx-auto max-w-6xl px-4 py-8 sm:px-6 lg:px-8">
      <header className="mb-6">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <h1 className="text-2xl font-semibold tracking-tight text-slate-900">
              Delivery Status Tracker
            </h1>
            <p className="mt-1 text-sm text-slate-600">
              {summaryQuery.data
                ? `${summaryQuery.data.total} shipments · lifecycle v${lifecycleQuery.data?.version ?? '–'}`
                : 'Loading shipments…'}
            </p>
          </div>
          <LifecycleRail lifecycle={lifecycleQuery.data} />
        </div>
      </header>

      <section className="card mb-4 p-4">
        <StatusFilterBar
          lifecycle={lifecycleQuery.data}
          summary={summaryQuery.data}
          selected={query.statuses}
          onChange={(statuses) => setQuery((current) => ({ ...current, statuses, page: 1 }))}
        />

        <div className="mt-4 flex flex-wrap items-center gap-3">
          <div className="relative min-w-56 flex-1">
            <span
              className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-400"
              aria-hidden
            >
              ⌕
            </span>
            <input
              type="search"
              className="field pl-8"
              placeholder="Search by reference or customer…"
              value={searchInput}
              onChange={(event) => setSearchInput(event.target.value)}
              aria-label="Search shipments"
            />
          </div>
          {activeFilters && (
            <button
              type="button"
              className="btn-ghost"
              onClick={() => {
                setSearchInput('')
                setQuery(DEFAULT_QUERY)
              }}
            >
              Clear filters
            </button>
          )}
        </div>
      </section>

      <section className="card overflow-hidden">
        {shipmentsQuery.isError && (
          <ErrorState
            message={(shipmentsQuery.error as ApiError)?.message ?? 'Failed to load shipments.'}
            onRetry={() => void shipmentsQuery.refetch()}
          />
        )}

        {shipmentsQuery.isPending && <SkeletonRows />}

        {shipmentsQuery.data && shipments.length === 0 && (
          <EmptyState
            activeFilters={activeFilters}
            onClear={() => {
              setSearchInput('')
              setQuery(DEFAULT_QUERY)
            }}
          />
        )}

        {shipments.length > 0 && (
          <ShipmentTable
            shipments={shipments}
            lifecycle={lifecycleQuery.data}
            sortBy={query.sortBy}
            sortDir={query.sortDir}
            onSort={onSort}
            pendingId={pendingShipmentId}
            onTransition={onTransition}
            onShowHistory={setHistoryFor}
            isRefreshing={shipmentsQuery.isFetching && !shipmentsQuery.isPending}
          />
        )}

        {meta && (
          <Pagination
            meta={meta}
            onPageChange={(page) => setQuery((current) => ({ ...current, page }))}
            onPageSizeChange={(pageSize) =>
              setQuery((current) => ({ ...current, pageSize, page: 1 }))
            }
          />
        )}
      </section>

      <HistoryDrawer
        shipment={historyFor}
        lifecycle={lifecycleQuery.data}
        onClose={() => setHistoryFor(null)}
      />

      {pending?.option.requires_reason && (
        <ReasonDialog
          shipment={pending.shipment}
          option={pending.option}
          submitting={updateStatus.isPending}
          onCancel={() => setPending(null)}
          onConfirm={(reason) => applyTransition(pending.shipment, pending.option, reason)}
        />
      )}
    </div>
  )
}

function SkeletonRows() {
  return (
    <div className="divide-y divide-slate-100">
      {Array.from({ length: 5 }).map((_, index) => (
        <div key={index} className="flex items-center gap-4 px-4 py-4">
          <div className="h-4 w-24 animate-pulse rounded bg-slate-100" />
          <div className="h-4 flex-1 animate-pulse rounded bg-slate-100" />
          <div className="h-6 w-24 animate-pulse rounded-full bg-slate-100" />
          <div className="h-8 w-32 animate-pulse rounded-lg bg-slate-100" />
        </div>
      ))}
    </div>
  )
}

function EmptyState({ activeFilters, onClear }: { activeFilters: boolean; onClear: () => void }) {
  return (
    <div className="px-4 py-16 text-center">
      <p className="text-sm font-medium text-slate-900">No shipments match this view</p>
      <p className="mt-1 text-sm text-slate-500">
        {activeFilters ? 'Try widening the filters.' : 'The database has no shipments loaded yet.'}
      </p>
      {activeFilters && (
        <button type="button" className="btn-secondary mt-4" onClick={onClear}>
          Clear filters
        </button>
      )}
    </div>
  )
}

function ErrorState({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <div className="px-4 py-16 text-center">
      <p className="text-sm font-medium text-rose-700">{message}</p>
      <button type="button" className="btn-secondary mt-4" onClick={onRetry}>
        Try again
      </button>
    </div>
  )
}
