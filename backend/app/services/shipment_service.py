"""Use cases for shipments.

This is the only place that combines the state machine with persistence:
routers stay thin, the repository stays SQL-only, and the lifecycle rules stay
in configuration.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.pagination import Page, PageParams
from app.db.models import Shipment, ShipmentEvent
from app.domain.errors import (
    ConcurrentUpdateError,
    ShipmentNotFoundError,
    UnknownStateError,
)
from app.domain.state_machine import StateMachine
from app.repositories.shipments import ShipmentFilters, ShipmentRepository
from app.schemas.shipment import (
    ShipmentEventRead,
    ShipmentRead,
    ShipmentSummary,
    StatusCount,
    StatusUpdateResponse,
    TransitionOption,
)

_REASON_GUARDS = frozenset({"require_reason"})


class ShipmentService:
    def __init__(self, session: AsyncSession, lifecycle: StateMachine) -> None:
        self._session = session
        self._lifecycle = lifecycle
        self._repo = ShipmentRepository(session)

    # ------------------------------------------------------------ read side

    async def list_shipments(
        self, filters: ShipmentFilters, params: PageParams
    ) -> Page[ShipmentRead]:
        self._assert_known_statuses(filters.statuses)

        rows, total = await self._repo.list_page(filters, params)
        last_events = await self._repo.latest_events_for([row.id for row in rows])
        items = [self._to_read(row, last_events.get(row.id)) for row in rows]
        return Page.build(items, total, params)

    async def get_shipment(self, shipment_id: uuid.UUID) -> ShipmentRead:
        shipment = await self._require(shipment_id)
        last_events = await self._repo.latest_events_for([shipment.id])
        return self._to_read(shipment, last_events.get(shipment.id))

    async def list_history(
        self, shipment_id: uuid.UUID, params: PageParams
    ) -> Page[ShipmentEventRead]:
        await self._require(shipment_id)
        rows, total = await self._repo.list_events_page(shipment_id, params)
        return Page.build(
            [ShipmentEventRead.model_validate(row) for row in rows], total, params
        )

    async def summary(self) -> ShipmentSummary:
        counts = await self._repo.count_by_status()
        # Report every configured status, including the ones with zero rows, so
        # the filter bar is stable as shipments move around.
        by_status = [
            StatusCount(status=state.code, count=counts.get(state.code, 0))
            for state in self._lifecycle.states
        ]
        return ShipmentSummary(total=sum(counts.values()), by_status=by_status)

    # ----------------------------------------------------------- write side

    async def change_status(
        self,
        shipment_id: uuid.UUID,
        *,
        target_status: str,
        reason: str | None,
        actor: str,
        expected_version: int | None = None,
    ) -> StatusUpdateResponse:
        """Validate against the state graph, then persist move + history atomically."""
        shipment = await self._require(shipment_id, for_update=True)

        if expected_version is not None and shipment.version != expected_version:
            raise ConcurrentUpdateError(
                f"Shipment {shipment.reference} has changed since you loaded it "
                f"(expected version {expected_version}, found {shipment.version}). "
                "Refresh and try again.",
                reference=shipment.reference,
                expected_version=expected_version,
                current_version=shipment.version,
                current_status=shipment.status,
            )

        transition = self._lifecycle.validate(
            shipment.status, target_status, reason=reason, actor=actor
        )

        event = await self._repo.apply_transition(
            shipment=shipment,
            target_status=transition.target,
            event=transition.event,
            reason=reason,
            actor=actor,
        )
        if event is None:
            raise ConcurrentUpdateError(
                f"Shipment {shipment.reference} was updated concurrently. "
                "Refresh and try again.",
                reference=shipment.reference,
            )

        await self._session.commit()
        return StatusUpdateResponse(
            shipment=self._to_read(shipment, event),
            event=ShipmentEventRead.model_validate(event),
        )

    # -------------------------------------------------------------- helpers

    async def _require(
        self, shipment_id: uuid.UUID, *, for_update: bool = False
    ) -> Shipment:
        shipment = await self._repo.get_by_id(shipment_id, for_update=for_update)
        if shipment is None:
            raise ShipmentNotFoundError(
                f"No shipment with id {shipment_id}.", shipment_id=str(shipment_id)
            )
        return shipment

    def _assert_known_statuses(self, statuses: Sequence[str]) -> None:
        unknown = [code for code in statuses if not self._lifecycle.has_state(code)]
        if unknown:
            raise UnknownStateError(
                f"Unknown status filter: {', '.join(unknown)}.",
                unknown_statuses=unknown,
                known_statuses=[state.code for state in self._lifecycle.states],
            )

    def _to_read(
        self, shipment: Shipment, last_event: ShipmentEvent | None
    ) -> ShipmentRead:
        return ShipmentRead(
            id=shipment.id,
            reference=shipment.reference,
            customer_name=shipment.customer_name,
            status=shipment.status,
            version=shipment.version,
            status_changed_at=shipment.status_changed_at,
            created_at=shipment.created_at,
            updated_at=shipment.updated_at,
            is_terminal=self._lifecycle.is_terminal(shipment.status),
            allowed_transitions=[
                TransitionOption(
                    target=transition.target,
                    event=transition.event,
                    label=transition.label,
                    description=transition.description,
                    requires_reason=bool(
                        _REASON_GUARDS.intersection(transition.guard_names)
                    ),
                )
                for transition in self._lifecycle.allowed_transitions(shipment.status)
            ],
            last_event=(
                ShipmentEventRead.model_validate(last_event) if last_event else None
            ),
        )
