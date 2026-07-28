import type { PageMeta } from '@/types/api'

interface Props {
  meta: PageMeta
  onPageChange: (page: number) => void
  onPageSizeChange?: (pageSize: number) => void
  pageSizes?: number[]
  label?: string
}

/** Page controls driven entirely by the server's page metadata. */
export function Pagination({
  meta,
  onPageChange,
  onPageSizeChange,
  pageSizes = [10, 20, 50],
  label = 'shipments',
}: Props) {
  const first = meta.total_items === 0 ? 0 : (meta.page - 1) * meta.page_size + 1
  const last = Math.min(meta.page * meta.page_size, meta.total_items)

  return (
    <div className="flex flex-wrap items-center justify-between gap-3 border-t border-slate-200 px-4 py-3">
      <p className="text-sm text-slate-600">
        {meta.total_items === 0 ? (
          <>No {label} to show</>
        ) : (
          <>
            Showing <span className="font-medium text-slate-900">{first}</span>–
            <span className="font-medium text-slate-900">{last}</span> of{' '}
            <span className="font-medium text-slate-900">{meta.total_items}</span> {label}
          </>
        )}
      </p>

      <div className="flex items-center gap-2">
        {onPageSizeChange && (
          <label className="mr-2 flex items-center gap-2 text-sm text-slate-600">
            Rows
            <select
              className="field w-auto py-1"
              value={meta.page_size}
              onChange={(event) => onPageSizeChange(Number(event.target.value))}
            >
              {pageSizes.map((size) => (
                <option key={size} value={size}>
                  {size}
                </option>
              ))}
            </select>
          </label>
        )}

        <button
          type="button"
          className="btn-secondary"
          onClick={() => onPageChange(meta.page - 1)}
          disabled={!meta.has_previous}
        >
          ← Previous
        </button>
        <span className="px-1 text-sm tabular-nums text-slate-600">
          Page {meta.total_pages === 0 ? 0 : meta.page} of {meta.total_pages}
        </span>
        <button
          type="button"
          className="btn-secondary"
          onClick={() => onPageChange(meta.page + 1)}
          disabled={!meta.has_next}
        >
          Next →
        </button>
      </div>
    </div>
  )
}
