"""CSV -> Postgres loader.

Idempotent by design: it upserts on `reference`, so re-running it (which the
API container does on every boot) never duplicates or resets demo data. A row
whose status has drifted from the CSV is left alone — the database is the
source of truth once a shipment is live, the CSV is only the initial import.

Statuses in the CSV are validated against the state machine, so a typo in the
file is a loud failure at import time rather than a bad row in the table.
"""

from __future__ import annotations

import csv
import logging
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Shipment
from app.domain.errors import DomainError
from app.domain.state_machine import StateMachine
from app.repositories.shipments import ShipmentRepository

logger = logging.getLogger(__name__)

REQUIRED_COLUMNS = {"reference", "customer_name", "status"}


class SeedError(DomainError):
    code = "seed_failed"
    http_status = 500


@dataclass(frozen=True, slots=True)
class SeedRow:
    reference: str
    customer_name: str
    status: str


@dataclass(frozen=True, slots=True)
class SeedReport:
    inserted: int
    skipped: int

    @property
    def total(self) -> int:
        return self.inserted + self.skipped


def parse_csv(path: Path, machine: StateMachine) -> list[SeedRow]:
    if not path.exists():
        raise SeedError(f"Seed CSV not found at {path}.")

    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        missing = REQUIRED_COLUMNS - set(reader.fieldnames or [])
        if missing:
            raise SeedError(
                f"Seed CSV {path.name} is missing column(s): {sorted(missing)}."
            )

        rows: list[SeedRow] = []
        seen: set[str] = set()
        for line_no, raw in enumerate(reader, start=2):
            reference = (raw.get("reference") or "").strip()
            customer = (raw.get("customer_name") or "").strip()
            status = (raw.get("status") or "").strip().lower()

            if not reference:
                raise SeedError(f"{path.name}:{line_no} has an empty reference.")
            if reference in seen:
                raise SeedError(f"{path.name}:{line_no} duplicates reference {reference}.")
            if not machine.has_state(status):
                raise SeedError(
                    f"{path.name}:{line_no} has status '{status}', which is not part "
                    f"of the '{machine.name}' lifecycle "
                    f"({', '.join(s.code for s in machine.states)})."
                )
            seen.add(reference)
            rows.append(SeedRow(reference, customer, status))

    return rows


async def seed_shipments(
    session: AsyncSession, machine: StateMachine, csv_path: Path
) -> SeedReport:
    rows = parse_csv(csv_path, machine)

    existing = set(
        (
            await session.execute(
                select(Shipment.reference).where(
                    Shipment.reference.in_([row.reference for row in rows])
                )
            )
        )
        .scalars()
        .all()
    )

    repo = ShipmentRepository(session)
    inserted = 0
    for row in rows:
        if row.reference in existing:
            continue
        shipment = Shipment(
            reference=row.reference,
            customer_name=row.customer_name,
            status=row.status,
        )
        session.add(shipment)
        await session.flush()
        # Give every shipment a first history entry so the timeline is never
        # empty, even for rows that arrive mid-lifecycle.
        await repo.record_creation_event(shipment, actor="csv-import")
        inserted += 1

    await session.flush()
    report = SeedReport(inserted=inserted, skipped=len(rows) - inserted)
    logger.info(
        "Seed complete: %d inserted, %d already present (%d rows in %s)",
        report.inserted,
        report.skipped,
        report.total,
        csv_path.name,
    )
    return report


async def count_shipments(session: AsyncSession) -> int:
    return int(await session.scalar(select(func.count()).select_from(Shipment)) or 0)
