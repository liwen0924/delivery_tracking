/** React Query bindings. Query keys mirror the server-side query parameters. */

import {
  keepPreviousData,
  useMutation,
  useQuery,
  useQueryClient,
} from '@tanstack/react-query'

import { api } from '@/api/client'
import type { ShipmentQuery, StatusUpdateResponse } from '@/types/api'

export const queryKeys = {
  lifecycle: ['lifecycle'] as const,
  shipments: (query: ShipmentQuery) => ['shipments', query] as const,
  summary: ['shipments', 'summary'] as const,
  events: (shipmentId: string, page: number) => ['shipments', shipmentId, 'events', page] as const,
}

export function useLifecycle() {
  return useQuery({
    queryKey: queryKeys.lifecycle,
    queryFn: api.lifecycle,
    // The state graph only changes when the config does, so cache it hard.
    staleTime: Infinity,
  })
}

export function useShipments(query: ShipmentQuery) {
  return useQuery({
    queryKey: queryKeys.shipments(query),
    queryFn: () => api.shipments(query),
    // Keeps the current page on screen while the next one loads.
    placeholderData: keepPreviousData,
  })
}

export function useSummary() {
  return useQuery({ queryKey: queryKeys.summary, queryFn: api.summary })
}

export function useShipmentEvents(shipmentId: string | null, page: number, pageSize = 10) {
  return useQuery({
    queryKey: queryKeys.events(shipmentId ?? '', page),
    queryFn: () => api.events(shipmentId as string, page, pageSize),
    enabled: Boolean(shipmentId),
    placeholderData: keepPreviousData,
  })
}

export function useUpdateStatus(onSuccess?: (result: StatusUpdateResponse) => void) {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (input: {
      shipmentId: string
      status: string
      reason?: string
      expectedVersion: number
    }) =>
      api.updateStatus(input.shipmentId, {
        status: input.status,
        reason: input.reason,
        expected_version: input.expectedVersion,
      }),
    onSuccess: (result) => {
      // Refetch rather than patch the cache: the server owns which transitions
      // are legal next, and the counts change too.
      void queryClient.invalidateQueries({ queryKey: ['shipments'] })
      onSuccess?.(result)
    },
  })
}
