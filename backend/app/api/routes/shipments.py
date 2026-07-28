"""Shipment endpoints.

Both collections are paginated server-side; there is no unbounded list route.
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, status

from app.api.deps import ShipmentServiceDep
from app.core.pagination import Page, PageParams, page_params
from app.repositories.shipments import ShipmentFilters, SortDirection, SortField
from app.schemas.shipment import (
    ShipmentEventRead,
    ShipmentRead,
    ShipmentSummary,
    StatusUpdateRequest,
    StatusUpdateResponse,
)

router = APIRouter(prefix="/shipments", tags=["shipments"])

PageDep = Annotated[PageParams, Depends(page_params)]
ShipmentId = Annotated[uuid.UUID, Path(description="Shipment UUID.")]


def shipment_filters(
    status: Annotated[
        list[str] | None,
        Query(description="Filter by status; repeat the parameter to OR several."),
    ] = None,
    search: Annotated[
        str | None, Query(max_length=120, description="Match reference or customer.")
    ] = None,
    sort_by: Annotated[SortField, Query()] = "reference",
    sort_dir: Annotated[SortDirection, Query()] = "asc",
) -> ShipmentFilters:
    return ShipmentFilters(
        statuses=tuple(dict.fromkeys(s.strip().lower() for s in status or [] if s.strip())),
        search=search,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )


FiltersDep = Annotated[ShipmentFilters, Depends(shipment_filters)]


@router.get(
    "",
    response_model=Page[ShipmentRead],
    summary="List shipments (paginated, filterable)",
)
async def list_shipments(
    service: ShipmentServiceDep, filters: FiltersDep, params: PageDep
) -> Page[ShipmentRead]:
    return await service.list_shipments(filters, params)


@router.get(
    "/summary",
    response_model=ShipmentSummary,
    summary="Counts per status across the whole collection",
)
async def shipment_summary(service: ShipmentServiceDep) -> ShipmentSummary:
    return await service.summary()


@router.get("/{shipment_id}", response_model=ShipmentRead, summary="Fetch one shipment")
async def get_shipment(service: ShipmentServiceDep, shipment_id: ShipmentId) -> ShipmentRead:
    return await service.get_shipment(shipment_id)


@router.get(
    "/{shipment_id}/events",
    response_model=Page[ShipmentEventRead],
    summary="Status history, newest first (paginated)",
)
async def list_shipment_events(
    service: ShipmentServiceDep, shipment_id: ShipmentId, params: PageDep
) -> Page[ShipmentEventRead]:
    return await service.list_history(shipment_id, params)


@router.post(
    "/{shipment_id}/status",
    response_model=StatusUpdateResponse,
    status_code=status.HTTP_200_OK,
    summary="Move a shipment to a new status",
    responses={
        404: {"description": "Shipment not found"},
        409: {"description": "Illegal transition, or the shipment changed concurrently"},
        422: {"description": "Unknown status, or a transition guard rejected the change"},
    },
)
async def update_shipment_status(
    service: ShipmentServiceDep, shipment_id: ShipmentId, payload: StatusUpdateRequest
) -> StatusUpdateResponse:
    return await service.change_status(
        shipment_id,
        target_status=payload.status,
        reason=payload.reason,
        actor=payload.actor,
        expected_version=payload.expected_version,
    )
