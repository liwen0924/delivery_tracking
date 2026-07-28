import type { LifecycleState } from '@/types/api'
import { statusDot, statusStyle } from '@/lib/lifecycle'

interface Props {
  state: LifecycleState
  size?: 'sm' | 'md'
}

export function StatusBadge({ state, size = 'md' }: Props) {
  const padding = size === 'sm' ? 'px-2 py-0.5 text-[11px]' : 'px-2.5 py-1 text-xs'
  return (
    <span
      title={state.description}
      className={`inline-flex items-center gap-1.5 rounded-full font-medium ring-1 ring-inset ${padding} ${statusStyle(state.tone)}`}
    >
      <span className={`h-1.5 w-1.5 rounded-full ${statusDot(state.tone)}`} aria-hidden />
      {state.label}
    </span>
  )
}
