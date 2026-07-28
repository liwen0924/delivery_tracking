"""ORM models.

Schema notes
------------
`shipment_status` and `shipment_status_transition` are lookup tables generated
from `config/shipment_lifecycle.yaml` on boot. They exist so the database can
enforce referential integrity on statuses (no free-text status can ever be
written) and so the transition table is inspectable with plain SQL — but the
YAML remains the single source of truth; the tables are a projection of it.

`shipment_event` is an append-only audit log. Status history is derived from
it rather than stored as a mutable field, which makes the history view a read
of the same rows the transition wrote.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

STATUS_LENGTH = 40


class ShipmentStatus(Base):
    """One row per state in the lifecycle graph."""

    __tablename__ = "shipment_status"

    code: Mapped[str] = mapped_column(String(STATUS_LENGTH), primary_key=True)
    label: Mapped[str] = mapped_column(String(80), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    is_initial: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_terminal: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    tone: Mapped[str] = mapped_column(String(20), nullable=False, default="neutral")
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class ShipmentStatusTransition(Base):
    """One row per legal edge of the lifecycle graph."""

    __tablename__ = "shipment_status_transition"
    __table_args__ = (
        CheckConstraint(
            "source_status <> target_status", name="no_self_transition"
        ),
        Index("ix_shipment_status_transition_source", "source_status"),
    )

    source_status: Mapped[str] = mapped_column(
        String(STATUS_LENGTH),
        ForeignKey("shipment_status.code", ondelete="CASCADE"),
        primary_key=True,
    )
    target_status: Mapped[str] = mapped_column(
        String(STATUS_LENGTH),
        ForeignKey("shipment_status.code", ondelete="CASCADE"),
        primary_key=True,
    )
    event: Mapped[str] = mapped_column(String(60), nullable=False)
    label: Mapped[str] = mapped_column(String(80), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")


class Shipment(Base, TimestampMixin):
    __tablename__ = "shipment"
    # Supports the common query shape: filter by status, order by reference.
    __table_args__ = (Index("ix_shipment_status_reference", "status", "reference"),)

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    reference: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    customer_name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(
        String(STATUS_LENGTH),
        ForeignKey("shipment_status.code", onupdate="CASCADE"),
        nullable=False,
    )
    # Optimistic lock: bumped on every status change so two concurrent updates
    # cannot silently overwrite each other.
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status_changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Status labels/tones are served once via GET /lifecycle and joined in the
    # client, so shipment reads stay single-table.
    events: Mapped[list[ShipmentEvent]] = relationship(
        back_populates="shipment",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="noload",
    )


class ShipmentEvent(Base):
    """Append-only status history. Never updated, never deleted."""

    __tablename__ = "shipment_event"
    __table_args__ = (
        ForeignKeyConstraint(
            ["source_status"], ["shipment_status.code"], onupdate="CASCADE"
        ),
        ForeignKeyConstraint(
            ["target_status"], ["shipment_status.code"], onupdate="CASCADE"
        ),
        # Covers "history for one shipment, newest first" with a keyset-friendly
        # tiebreaker on the monotonic id.
        Index("ix_shipment_event_shipment_recent", "shipment_id", "occurred_at", "id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    shipment_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("shipment.id", ondelete="CASCADE"),
        nullable=False,
    )
    # NULL source means "shipment came into existence in this status".
    source_status: Mapped[str | None] = mapped_column(String(STATUS_LENGTH))
    target_status: Mapped[str] = mapped_column(String(STATUS_LENGTH), nullable=False)
    event: Mapped[str] = mapped_column(String(60), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text)
    actor: Mapped[str] = mapped_column(String(120), nullable=False, default="system")
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    shipment: Mapped[Shipment] = relationship(back_populates="events")
