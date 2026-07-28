"""Data access for shipments and their event history.

The repository owns SQL and nothing else: no HTTP concepts, no lifecycle rules.
Every collection method takes `PageParams` and returns `(rows, total)` — there
is deliberately no "fetch all" method to reach for.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

from sqlalchemy import Select, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.pagination import PageParams
from app.db.models import Shipment, ShipmentEvent

SortField = Literal["reference", "customer_name", "status", "status_changed_at", "created_at"]
SortDirection = Literal["asc", "desc"]

_SORT_COLUMNS = {
    "reference": Shipment.reference,
    "customer_name": Shipment.customer_name,
    "status": Shipment.status,
    "status_changed_at": Shipment.status_changed_at,
    "created_at": Shipment.created_at,
}


@dataclass(frozen=True, slots=True)
class ShipmentFilters:
    statuses: tuple[str, ...] = ()
    search: str | None = None
    sort_by: SortField = "reference"
    sort_dir: SortDirection = "asc"


class ShipmentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # ------------------------------------------------------------- queries

    def _apply_filters(self, stmt: Select, filters: ShipmentFilters) -> Select:
        if filters.statuses:
            stmt = stmt.where(Shipment.status.in_(filters.statuses))
        if filters.search:
            term = f"%{filters.search.strip()}%"
            stmt = stmt.where(
                or_(
                    Shipment.reference.ilike(term),
                    Shipment.customer_name.ilike(term),
                )
            )
        return stmt

    async def list_page(
        self, filters: ShipmentFilters, params: PageParams
    ) -> tuple[Sequence[Shipment], int]:
        total = await self._session.scalar(
            self._apply_filters(select(func.count()).select_from(Shipment), filters)
        )

        column = _SORT_COLUMNS[filters.sort_by]
        order = column.asc() if filters.sort_dir == "asc" else column.desc()

        stmt = (
            self._apply_filters(select(Shipment), filters)
            # Reference is unique, so this second key makes the ordering total
            # and therefore the pagination stable across pages.
            .order_by(order, Shipment.reference.asc())
            .offset(params.offset)
            .limit(params.limit)
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return rows, int(total or 0)

    async def count_by_status(self) -> dict[str, int]:
        rows = await self._session.execute(
            select(Shipment.status, func.count()).group_by(Shipment.status)
        )
        return {status: int(count) for status, count in rows.all()}

    async def get_by_id(
        self, shipment_id: uuid.UUID, *, for_update: bool = False
    ) -> Shipment | None:
        stmt = select(Shipment).where(Shipment.id == shipment_id)
        if for_update:
            # Serialises concurrent transitions on the same shipment row.
            stmt = stmt.with_for_update()
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def get_by_reference(self, reference: str) -> Shipment | None:
        stmt = select(Shipment).where(Shipment.reference == reference)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def list_events_page(
        self, shipment_id: uuid.UUID, params: PageParams
    ) -> tuple[Sequence[ShipmentEvent], int]:
        total = await self._session.scalar(
            select(func.count())
            .select_from(ShipmentEvent)
            .where(ShipmentEvent.shipment_id == shipment_id)
        )
        stmt = (
            select(ShipmentEvent)
            .where(ShipmentEvent.shipment_id == shipment_id)
            .order_by(ShipmentEvent.occurred_at.desc(), ShipmentEvent.id.desc())
            .offset(params.offset)
            .limit(params.limit)
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return rows, int(total or 0)

    async def latest_events_for(
        self, shipment_ids: Sequence[uuid.UUID]
    ) -> dict[uuid.UUID, ShipmentEvent]:
        """Most recent event per shipment in one round trip, avoiding an N+1.

        Uses Postgres DISTINCT ON, which the (shipment_id, occurred_at, id)
        index serves directly.
        """
        if not shipment_ids:
            return {}
        stmt = (
            select(ShipmentEvent)
            .where(ShipmentEvent.shipment_id.in_(shipment_ids))
            .distinct(ShipmentEvent.shipment_id)
            .order_by(
                ShipmentEvent.shipment_id,
                ShipmentEvent.occurred_at.desc(),
                ShipmentEvent.id.desc(),
            )
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return {event.shipment_id: event for event in rows}

    # ------------------------------------------------------------- mutation

    async def apply_transition(
        self,
        *,
        shipment: Shipment,
        target_status: str,
        event: str,
        reason: str | None,
        actor: str,
    ) -> ShipmentEvent | None:
        """Move the shipment and append the matching history row.

        The caller's transaction wraps both writes, so a shipment can never end
        up in a status without the event that put it there.
        """
        now = datetime.now(UTC)
        source_status = shipment.status

        result = await self._session.execute(
            update(Shipment)
            .where(Shipment.id == shipment.id, Shipment.version == shipment.version)
            .values(
                status=target_status,
                version=Shipment.version + 1,
                status_changed_at=now,
                updated_at=now,
            )
            .returning(Shipment.version)
        )
        new_version = result.scalar_one_or_none()
        if new_version is None:
            # Version moved under us: the caller turns this into a 409.
            return None

        history = ShipmentEvent(
            shipment_id=shipment.id,
            source_status=source_status,
            target_status=target_status,
            event=event,
            reason=reason,
            actor=actor,
            occurred_at=now,
        )
        self._session.add(history)
        await self._session.flush()

        shipment.status = target_status
        shipment.version = new_version
        shipment.status_changed_at = now
        return history

    async def record_creation_event(self, shipment: Shipment, actor: str = "system") -> None:
        self._session.add(
            ShipmentEvent(
                shipment_id=shipment.id,
                source_status=None,
                target_status=shipment.status,
                event="import",
                reason="Imported from shipments.csv",
                actor=actor,
            )
        )
