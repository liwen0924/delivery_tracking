"""FastAPI dependencies."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session_factory
from app.domain.lifecycle import get_shipment_lifecycle
from app.domain.state_machine import StateMachine
from app.services.shipment_service import ShipmentService


async def get_session() -> AsyncIterator[AsyncSession]:
    """One session per request; rolled back unless the service commits."""
    async with get_session_factory()() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


SessionDep = Annotated[AsyncSession, Depends(get_session)]
LifecycleDep = Annotated[StateMachine, Depends(get_shipment_lifecycle)]


def get_shipment_service(
    session: SessionDep, lifecycle: LifecycleDep
) -> ShipmentService:
    return ShipmentService(session, lifecycle)


ShipmentServiceDep = Annotated[ShipmentService, Depends(get_shipment_service)]
