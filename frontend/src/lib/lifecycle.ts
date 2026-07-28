/**
 * Presentation helpers derived from the lifecycle the API serves.
 *
 * Labels and colours are keyed off the `tone` each state declares in
 * `shipment_lifecycle.yaml`, so adding a state to the config gives it a chip
 * in the UI without a frontend change.
 */

import type { Lifecycle, LifecycleState, StatusTone } from '@/types/api'

const TONE_STYLES: Record<StatusTone, string> = {
  neutral: 'bg-slate-100 text-slate-700 ring-slate-200',
  info: 'bg-sky-50 text-sky-700 ring-sky-200',
  progress: 'bg-amber-50 text-amber-800 ring-amber-200',
  success: 'bg-emerald-50 text-emerald-700 ring-emerald-200',
  danger: 'bg-rose-50 text-rose-700 ring-rose-200',
}

const TONE_DOTS: Record<StatusTone, string> = {
  neutral: 'bg-slate-400',
  info: 'bg-sky-500',
  progress: 'bg-amber-500',
  success: 'bg-emerald-500',
  danger: 'bg-rose-500',
}

const FALLBACK: LifecycleState = {
  code: 'unknown',
  label: 'Unknown',
  description: '',
  initial: false,
  terminal: false,
  tone: 'neutral',
  position: 999,
  allowed_targets: [],
}

export function statusStyle(tone: StatusTone): string {
  return TONE_STYLES[tone] ?? TONE_STYLES.neutral
}

export function statusDot(tone: StatusTone): string {
  return TONE_DOTS[tone] ?? TONE_DOTS.neutral
}

export function stateOf(lifecycle: Lifecycle | undefined, code: string | null): LifecycleState {
  if (!code) return FALLBACK
  return lifecycle?.states.find((state) => state.code === code) ?? { ...FALLBACK, code, label: code }
}

/** Ordered states, for the filter bar and the progress rail. */
export function orderedStates(lifecycle: Lifecycle | undefined): LifecycleState[] {
  return [...(lifecycle?.states ?? [])].sort((a, b) => a.position - b.position)
}

/** The linear "happy path" from the initial state, used by the progress rail. */
export function mainPath(lifecycle: Lifecycle | undefined): string[] {
  if (!lifecycle) return []
  const path: string[] = []
  let current: string | undefined = lifecycle.initial_state

  while (current && !path.includes(current)) {
    path.push(current)
    const next: string | undefined = lifecycle.transitions.find(
      (transition) =>
        transition.source === current &&
        !lifecycle.states.find((state) => state.code === transition.target)?.terminal,
    )?.target
    if (next) {
      current = next
      continue
    }
    // No non-terminal successor: finish on the terminal state that is not the
    // failure branch (i.e. the one reachable from here).
    current = lifecycle.transitions.find(
      (transition) =>
        transition.source === current &&
        lifecycle.states.find((state) => state.code === transition.target)?.tone === 'success',
    )?.target
  }
  return path
}
