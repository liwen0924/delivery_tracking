"""Liveness and readiness probes (readiness is what compose waits on)."""

from __future__ import annotations

from fastapi import APIRouter, status
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.api.deps import SessionDep

router = APIRouter(tags=["system"])


@router.get("/health", summary="Liveness")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/ready", summary="Readiness (checks the database)")
async def ready(session: SessionDep) -> JSONResponse:
    try:
        await session.execute(text("SELECT 1"))
    except Exception as exc:  # noqa: BLE001 - probe must never raise
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "unavailable", "database": str(exc)},
        )
    return JSONResponse(content={"status": "ready", "database": "ok"})
