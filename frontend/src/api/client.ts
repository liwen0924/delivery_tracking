/**
 * Thin fetch wrapper.
 *
 * The API returns one error envelope for every failure, so this is the single
 * place that unwraps it into an `ApiError` the UI can render — no per-call
 * error handling anywhere else.
 */

import type {
  Lifecycle,
  Page,
  Shipment,
  ShipmentEvent,
  ShipmentQuery,
  ShipmentSummary,
  StatusUpdateResponse,
} from '@/types/api'

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? '/api/v1'

interface ErrorEnvelope {
  error?: { code?: string; message?: string; details?: Record<string, unknown> }
}

export class ApiError extends Error {
  readonly code: string
  readonly status: number
  readonly details: Record<string, unknown>

  constructor(status: number, code: string, message: string, details: Record<string, unknown>) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
    this.details = details
  }

  /** Statuses the server says are reachable, when it rejected a transition. */
  get allowedTargets(): string[] {
    const targets = this.details.allowed_targets
    return Array.isArray(targets) ? (targets as string[]) : []
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response
  try {
    response = await fetch(`${API_BASE}${path}`, {
      ...init,
      headers: { 'Content-Type': 'application/json', ...init?.headers },
    })
  } catch {
    throw new ApiError(0, 'network_error', 'Cannot reach the API. Is it running?', {})
  }

  if (response.status === 204) return undefined as T

  const body = (await response.json().catch(() => ({}))) as ErrorEnvelope & T
  if (!response.ok) {
    throw new ApiError(
      response.status,
      body.error?.code ?? 'unknown_error',
      body.error?.message ?? `Request failed with status ${response.status}.`,
      body.error?.details ?? {},
    )
  }
  return body as T
}

function shipmentSearchParams(query: ShipmentQuery): URLSearchParams {
  const params = new URLSearchParams({
    page: String(query.page),
    page_size: String(query.pageSize),
    sort_by: query.sortBy,
    sort_dir: query.sortDir,
  })
  // Repeated `status` params are OR-ed server-side.
  query.statuses.forEach((status) => params.append('status', status))
  if (query.search.trim()) params.set('search', query.search.trim())
  return params
}

export const api = {
  lifecycle: () => request<Lifecycle>('/lifecycle'),

  shipments: (query: ShipmentQuery) =>
    request<Page<Shipment>>(`/shipments?${shipmentSearchParams(query)}`),

  summary: () => request<ShipmentSummary>('/shipments/summary'),

  events: (shipmentId: string, page: number, pageSize: number) =>
    request<Page<ShipmentEvent>>(
      `/shipments/${shipmentId}/events?page=${page}&page_size=${pageSize}`,
    ),

  updateStatus: (
    shipmentId: string,
    payload: { status: string; reason?: string; expected_version: number },
  ) =>
    request<StatusUpdateResponse>(`/shipments/${shipmentId}/status`, {
      method: 'POST',
      body: JSON.stringify({ actor: 'web-ui', ...payload }),
    }),
}
