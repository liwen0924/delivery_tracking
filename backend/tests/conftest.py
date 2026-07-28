"""Test fixtures.

Unit tests (the state machine) need nothing. API tests run against a real
PostgreSQL — the same engine as production, because transition validation,
foreign keys and `SELECT ... FOR UPDATE` are exactly what we want covered. If
no database is reachable the API tests skip with a clear reason instead of
failing the whole run.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator

TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://tracker:tracker@localhost:5432/tracker_test",
)
# Must be set before app modules read settings.
os.environ["DATABASE_URL"] = TEST_DATABASE_URL

import pytest  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy import text  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: E402

from app.db.base import Base  # noqa: E402
from app.db.lifecycle_sync import sync_lifecycle  # noqa: E402
from app.db.models import Shipment  # noqa: E402
from app.db.session import dispose_engine, get_engine, session_scope  # noqa: E402
from app.domain.lifecycle import load_state_machine  # noqa: E402
from app.main import create_app  # noqa: E402
from app.repositories.shipments import ShipmentRepository  # noqa: E402

SEED = [
    ("TV-9001", "Summit Logistics", "created"),
    ("TV-9002", "Eastlink Retail", "picked_up"),
    ("TV-9003", "Baywater Supplies", "in_transit"),
    ("TV-9004", "Northern Trading", "delivered"),
    ("TV-9005", "Silverline Trading", "failed"),
]


@pytest.fixture(scope="session")
def lifecycle():
    return load_state_machine()


@pytest.fixture(scope="session")
async def database(lifecycle):
    """Create a clean schema for the session, or skip if there is no database."""
    engine = get_engine()
    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.drop_all)
            await connection.run_sync(Base.metadata.create_all)
    except Exception as exc:  # noqa: BLE001
        await dispose_engine()
        pytest.skip(
            "PostgreSQL is not reachable at "
            f"{TEST_DATABASE_URL.rsplit('@', 1)[-1]} ({type(exc).__name__}). "
            "Start it with `make up` or run `make test` to use the compose database."
        )

    async with session_scope() as session:
        await sync_lifecycle(session, lifecycle)

    yield engine
    await dispose_engine()


@pytest.fixture
async def seeded(database) -> AsyncIterator[dict[str, Shipment]]:
    """Fresh shipment rows per test; the event log is truncated with them."""
    async with session_scope() as session:
        await session.execute(
            text("TRUNCATE shipment_event, shipment RESTART IDENTITY CASCADE")
        )
        repo = ShipmentRepository(session)
        created: dict[str, Shipment] = {}
        for reference, customer, status in SEED:
            shipment = Shipment(reference=reference, customer_name=customer, status=status)
            session.add(shipment)
            await session.flush()
            await repo.record_creation_event(shipment, actor="test-fixture")
            created[reference] = shipment

    yield created


@pytest.fixture
async def client(database) -> AsyncIterator[AsyncClient]:
    app = create_app()
    transport = ASGITransport(app=app)
    async with (
        app.router.lifespan_context(app),
        AsyncClient(transport=transport, base_url="http://test") as http,
    ):
        yield http


@pytest.fixture
async def session(database) -> AsyncIterator[AsyncSession]:
    async with session_scope() as db_session:
        yield db_session
