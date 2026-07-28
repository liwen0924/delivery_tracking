"""Projects the YAML state graph onto the database lookup tables.

Runs on every boot and is idempotent, so editing `shipment_lifecycle.yaml` and
restarting is all it takes to change the state graph — including the foreign
keys that stop an unknown status from ever being written.

Rows that disappear from the config are only removed when nothing references
them; otherwise we fail loudly rather than orphan live data.
"""

from __future__ import annotations

import logging

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Shipment, ShipmentStatus, ShipmentStatusTransition
from app.domain.errors import LifecycleConfigError
from app.domain.state_machine import StateMachine

logger = logging.getLogger(__name__)


async def sync_lifecycle(session: AsyncSession, machine: StateMachine) -> None:
    await _sync_states(session, machine)
    await _sync_transitions(session, machine)
    await session.flush()
    logger.info(
        "Lifecycle '%s' v%s synced: %d states, %d transitions",
        machine.name,
        machine.version,
        len(machine.states),
        len(machine.transitions),
    )


async def _sync_states(session: AsyncSession, machine: StateMachine) -> None:
    rows = [
        {
            "code": state.code,
            "label": state.label,
            "description": state.description,
            "is_initial": state.initial,
            "is_terminal": state.terminal,
            "tone": state.tone,
            "position": state.position,
        }
        for state in machine.states
    ]
    stmt = insert(ShipmentStatus).values(rows)
    await session.execute(
        stmt.on_conflict_do_update(
            index_elements=[ShipmentStatus.code],
            set_={
                column: stmt.excluded[column]
                for column in (
                    "label",
                    "description",
                    "is_initial",
                    "is_terminal",
                    "tone",
                    "position",
                )
            },
        )
    )

    configured = {state.code for state in machine.states}
    stale = (
        await session.execute(
            select(ShipmentStatus.code).where(ShipmentStatus.code.notin_(configured))
        )
    ).scalars().all()
    if not stale:
        return

    in_use = (
        await session.execute(
            select(Shipment.status, func.count())
            .where(Shipment.status.in_(stale))
            .group_by(Shipment.status)
        )
    ).all()
    if in_use:
        raise LifecycleConfigError(
            "Cannot remove status(es) still referenced by shipments: "
            + ", ".join(f"{code} ({count})" for code, count in in_use)
        )

    await session.execute(delete(ShipmentStatus).where(ShipmentStatus.code.in_(stale)))
    logger.warning("Removed statuses no longer present in the config: %s", stale)


async def _sync_transitions(session: AsyncSession, machine: StateMachine) -> None:
    # The transition table is fully derived, so a replace keeps it exact.
    await session.execute(delete(ShipmentStatusTransition))
    if not machine.transitions:
        return
    await session.execute(
        insert(ShipmentStatusTransition).values(
            [
                {
                    "source_status": transition.source,
                    "target_status": transition.target,
                    "event": transition.event,
                    "label": transition.label,
                    "description": transition.description,
                }
                for transition in machine.transitions
            ]
        )
    )
