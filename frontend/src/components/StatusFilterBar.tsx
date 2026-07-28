import type { Lifecycle, ShipmentSummary } from '@/types/api'
import { orderedStates, statusDot } from '@/lib/lifecycle'

interface Props {
  lifecycle: Lifecycle | undefined
  summary: ShipmentSummary | undefined
  selected: string[]
  onChange: (statuses: string[]) => void
}

/**
 * Multi-select status filter. Both the chips and the counts come from the
 * server, so a new state in the lifecycle config appears here automatically.
 */
export function StatusFilterBar({ lifecycle, summary, selected, onChange }: Props) {
  const counts = new Map(summary?.by_status.map((row) => [row.status, row.count]))

  const toggle = (code: string) => {
    onChange(
      selected.includes(code) ? selected.filter((item) => item !== code) : [...selected, code],
    )
  }

  return (
    <div className="flex flex-wrap items-center gap-2">
      <FilterChip
        label="All"
        count={summary?.total}
        active={selected.length === 0}
        onClick={() => onChange([])}
      />
      {orderedStates(lifecycle).map((state) => (
        <FilterChip
          key={state.code}
          label={state.label}
          title={state.description}
          count={counts.get(state.code)}
          active={selected.includes(state.code)}
          dotClass={statusDot(state.tone)}
          onClick={() => toggle(state.code)}
        />
      ))}
    </div>
  )
}

interface ChipProps {
  label: string
  count?: number
  active: boolean
  onClick: () => void
  dotClass?: string
  title?: string
}

function FilterChip({ label, count, active, onClick, dotClass, title }: ChipProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      title={title}
      aria-pressed={active}
      className={`inline-flex items-center gap-2 rounded-full border px-3 py-1.5 text-sm font-medium transition-colors ${
        active
          ? 'border-indigo-600 bg-indigo-600 text-white shadow-sm'
          : 'border-slate-200 bg-white text-slate-700 hover:border-slate-300 hover:bg-slate-50'
      }`}
    >
      {dotClass && (
        <span
          className={`h-1.5 w-1.5 rounded-full ${active ? 'bg-white/80' : dotClass}`}
          aria-hidden
        />
      )}
      {label}
      {count !== undefined && (
        <span
          className={`rounded-full px-1.5 py-0.5 text-[11px] tabular-nums ${
            active ? 'bg-white/20 text-white' : 'bg-slate-100 text-slate-600'
          }`}
        >
          {count}
        </span>
      )}
    </button>
  )
}
