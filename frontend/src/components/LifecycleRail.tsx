import type { Lifecycle } from '@/types/api'
import { mainPath, stateOf, statusDot } from '@/lib/lifecycle'

/**
 * Renders the configured happy path plus its failure branch, so the rules the
 * API enforces are visible on screen. Derived from the lifecycle endpoint —
 * nothing about the graph is hard-coded here.
 */
export function LifecycleRail({ lifecycle }: { lifecycle: Lifecycle | undefined }) {
  if (!lifecycle) return null

  const path = mainPath(lifecycle)
  const failure = lifecycle.states.find((state) => state.tone === 'danger')

  return (
    <div className="flex flex-wrap items-center gap-2 rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs text-slate-600 shadow-sm">
      {path.map((code, index) => {
        const state = stateOf(lifecycle, code)
        return (
          <span key={code} className="flex items-center gap-2">
            {index > 0 && (
              <span className="text-slate-300" aria-hidden>
                →
              </span>
            )}
            <span className="inline-flex items-center gap-1.5" title={state.description}>
              <span className={`h-1.5 w-1.5 rounded-full ${statusDot(state.tone)}`} aria-hidden />
              {state.label}
            </span>
          </span>
        )
      })}
      {failure && (
        <span className="ml-1 inline-flex items-center gap-1.5 border-l border-slate-200 pl-3 text-slate-500">
          <span className={`h-1.5 w-1.5 rounded-full ${statusDot(failure.tone)}`} aria-hidden />
          {failure.label} from any non-terminal step
        </span>
      )}
    </div>
  )
}
