/** Mirrors the FastAPI response models in `backend/app/schemas`. */

export interface PageMeta {
  page: number
  page_size: number
  total_items: number
  total_pages: number
  has_previous: boolean
  has_next: boolean
}

export interface Page<T> {
  items: T[]
  meta: PageMeta
}

export type StatusTone = 'neutral' | 'info' | 'progress' | 'success' | 'danger'

export interface LifecycleState {
  code: string
  label: string
  description: string
  initial: boolean
  terminal: boolean
  tone: StatusTone
  position: number
  allowed_targets: string[]
}

export interface LifecycleTransition {
  event: string
  label: string
  source: string
  target: string
  description: string
  guards: string[]
}

export interface Lifecycle {
  name: string
  version: number
  initial_state: string
  states: LifecycleState[]
  transitions: LifecycleTransition[]
}

export interface TransitionOption {
  target: string
  event: string
  label: string
  description: string
  requires_reason: boolean
}

export interface ShipmentEvent {
  id: number
  source_status: string | null
  target_status: string
  event: string
  reason: string | null
  actor: string
  occurred_at: string
}

export interface Shipment {
  id: string
  reference: string
  customer_name: string
  status: string
  version: number
  status_changed_at: string
  created_at: string
  updated_at: string
  allowed_transitions: TransitionOption[]
  is_terminal: boolean
  last_event: ShipmentEvent | null
}

export interface StatusUpdateResponse {
  shipment: Shipment
  event: ShipmentEvent
}

export interface ShipmentSummary {
  total: number
  by_status: { status: string; count: number }[]
}

export type SortField =
  | 'reference'
  | 'customer_name'
  | 'status'
  | 'status_changed_at'
  | 'created_at'

export interface ShipmentQuery {
  page: number
  pageSize: number
  statuses: string[]
  search: string
  sortBy: SortField
  sortDir: 'asc' | 'desc'
}
