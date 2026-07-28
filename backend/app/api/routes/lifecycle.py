"""Exposes the state graph so clients can be config-driven too."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import LifecycleDep
from app.schemas.lifecycle import LifecycleRead

router = APIRouter(prefix="/lifecycle", tags=["lifecycle"])


@router.get(
    "",
    response_model=LifecycleRead,
    summary="The shipment state graph (states, transitions, guards)",
)
async def read_lifecycle(lifecycle: LifecycleDep) -> LifecycleRead:
    return LifecycleRead.model_validate(lifecycle.to_graph())
