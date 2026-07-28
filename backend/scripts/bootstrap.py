"""One-shot database bootstrap: wait -> migrate -> sync lifecycle -> seed.

Run by the API container before uvicorn starts, and available by hand via
`make seed`. Every step is idempotent, so it is safe on every boot.

    python -m scripts.bootstrap [--skip-seed] [--wait-seconds 60]
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import text

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.db.lifecycle_sync import sync_lifecycle
from app.db.seed import count_shipments, seed_shipments
from app.db.session import dispose_engine, get_engine, session_scope
from app.domain.lifecycle import load_state_machine

BACKEND_ROOT = Path(__file__).resolve().parents[1]
logger = logging.getLogger("bootstrap")


async def wait_for_database(timeout_seconds: int) -> None:
    engine = get_engine()
    deadline = asyncio.get_running_loop().time() + timeout_seconds
    attempt = 0
    while True:
        attempt += 1
        try:
            async with engine.connect() as connection:
                await connection.execute(text("SELECT 1"))
            logger.info("Database reachable after %d attempt(s).", attempt)
            return
        except Exception as exc:  # noqa: BLE001 - retry on any connection failure
            if asyncio.get_running_loop().time() >= deadline:
                raise RuntimeError(
                    f"Database not reachable after {timeout_seconds}s: {exc}"
                ) from exc
            logger.info("Waiting for database (attempt %d)...", attempt)
            await asyncio.sleep(1.0)


def run_migrations() -> None:
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_ROOT / "migrations"))
    # This process already configured logging; see migrations/env.py.
    config.attributes["configure_logger"] = False
    command.upgrade(config, "head")
    logger.info("Migrations at head.")


async def main(skip_seed: bool, wait_seconds: int) -> int:
    settings = get_settings()
    configure_logging(settings.debug)
    logger.info("Bootstrapping against %s", _safe_dsn(settings.database_url))

    await wait_for_database(wait_seconds)
    # Alembic is synchronous; run it off the event loop.
    await asyncio.to_thread(run_migrations)

    machine = load_state_machine()
    async with session_scope() as session:
        await sync_lifecycle(session, machine)
        if not skip_seed:
            await seed_shipments(session, machine, settings.seed_csv_path)

    async with session_scope() as session:
        logger.info("Ready: %d shipments in the database.", await count_shipments(session))

    await dispose_engine()
    return 0


def _safe_dsn(dsn: str) -> str:
    if "@" not in dsn:
        return dsn
    scheme, _, rest = dsn.partition("://")
    return f"{scheme}://***@{rest.rpartition('@')[2]}"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--skip-seed", action="store_true", help="Migrate but do not import the CSV."
    )
    parser.add_argument("--wait-seconds", type=int, default=60)
    args = parser.parse_args()
    sys.exit(asyncio.run(main(args.skip_seed, args.wait_seconds)))
