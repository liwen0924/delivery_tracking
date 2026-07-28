const RELATIVE = new Intl.RelativeTimeFormat(undefined, { numeric: 'auto' })
const ABSOLUTE = new Intl.DateTimeFormat(undefined, {
  dateStyle: 'medium',
  timeStyle: 'short',
})

const DIVISIONS: [Intl.RelativeTimeFormatUnit, number][] = [
  ['second', 60],
  ['minute', 60],
  ['hour', 24],
  ['day', 7],
  ['week', 4.34524],
  ['month', 12],
  ['year', Number.POSITIVE_INFINITY],
]

export function formatRelative(iso: string): string {
  let delta = (new Date(iso).getTime() - Date.now()) / 1000
  for (const [unit, span] of DIVISIONS) {
    if (Math.abs(delta) < span) return RELATIVE.format(Math.round(delta), unit)
    delta /= span
  }
  return ABSOLUTE.format(new Date(iso))
}

export function formatAbsolute(iso: string): string {
  return ABSOLUTE.format(new Date(iso))
}
