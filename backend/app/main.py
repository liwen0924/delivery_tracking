"""FastAPI application factory."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.errors import register_exception_handlers
from app.api.routes import health, lifecycle, shipments
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.db.session import dispose_engine
from app.domain.lifecycle import load_state_machine

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    configure_logging(settings.debug)
    # Fail fast on a broken state graph rather than on the first transition.
    machine = load_state_machine()
    logger.info(
        "Loaded '%s' lifecycle v%s (%d states, %d transitions)",
        machine.name,
        machine.version,
        len(machine.states),
        len(machine.transitions),
    )
    try:
        yield
    finally:
        await dispose_engine()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version="1.0.0",
        description=(
            "Delivery status tracking API. Status changes are validated against "
            "a configuration-driven state machine; every list endpoint is "
            "paginated server-side."
        ),
        lifespan=lifespan,
        docs_url="/docs",
        openapi_url="/openapi.json",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_exception_handlers(app)

    api = APIRouter(prefix=settings.api_prefix)
    api.include_router(health.router)
    api.include_router(lifecycle.router)
    api.include_router(shipments.router)
    app.include_router(api)

    return app


app = create_app()
