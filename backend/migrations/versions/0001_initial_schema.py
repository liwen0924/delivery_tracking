"""Initial delivery-tracking schema.

Creates the lifecycle lookup tables (populated at boot from
config/shipment_lifecycle.yaml), the shipments table, and the append-only
event log that backs the status-history view.

Revision ID: 0001
Revises:
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: str | None = None
branch_labels = None
depends_on = None

STATUS = sa.String(40)


def upgrade() -> None:
    op.create_table(
        "shipment_status",
        sa.Column("code", STATUS, nullable=False),
        sa.Column("label", sa.String(80), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("is_initial", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_terminal", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("tone", sa.String(20), nullable=False, server_default="neutral"),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.PrimaryKeyConstraint("code", name=op.f("pk_shipment_status")),
    )

    op.create_table(
        "shipment_status_transition",
        sa.Column("source_status", STATUS, nullable=False),
        sa.Column("target_status", STATUS, nullable=False),
        sa.Column("event", sa.String(60), nullable=False),
        sa.Column("label", sa.String(80), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.CheckConstraint(
            "source_status <> target_status",
            name=op.f("ck_shipment_status_transition_no_self_transition"),
        ),
        sa.ForeignKeyConstraint(
            ["source_status"],
            ["shipment_status.code"],
            name=op.f("fk_shipment_status_transition_source_status_shipment_status"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["target_status"],
            ["shipment_status.code"],
            name=op.f("fk_shipment_status_transition_target_status_shipment_status"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "source_status", "target_status", name=op.f("pk_shipment_status_transition")
        ),
    )
    op.create_index(
        "ix_shipment_status_transition_source",
        "shipment_status_transition",
        ["source_status"],
    )

    op.create_table(
        "shipment",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("reference", sa.String(64), nullable=False),
        sa.Column("customer_name", sa.String(255), nullable=False),
        sa.Column("status", STATUS, nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "status_changed_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["status"],
            ["shipment_status.code"],
            name=op.f("fk_shipment_status_shipment_status"),
            onupdate="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_shipment")),
        sa.UniqueConstraint("reference", name=op.f("uq_shipment_reference")),
    )
    op.create_index("ix_shipment_status_reference", "shipment", ["status", "reference"])

    op.create_table(
        "shipment_event",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("shipment_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_status", STATUS, nullable=True),
        sa.Column("target_status", STATUS, nullable=False),
        sa.Column("event", sa.String(60), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("actor", sa.String(120), nullable=False, server_default="system"),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["shipment_id"],
            ["shipment.id"],
            name=op.f("fk_shipment_event_shipment_id_shipment"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["source_status"],
            ["shipment_status.code"],
            name=op.f("fk_shipment_event_source_status_shipment_status"),
            onupdate="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["target_status"],
            ["shipment_status.code"],
            name=op.f("fk_shipment_event_target_status_shipment_status"),
            onupdate="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_shipment_event")),
    )
    op.create_index(
        "ix_shipment_event_shipment_recent",
        "shipment_event",
        ["shipment_id", "occurred_at", "id"],
    )


def downgrade() -> None:
    op.drop_table("shipment_event")
    op.drop_index("ix_shipment_status_reference", table_name="shipment")
    op.drop_table("shipment")
    op.drop_index(
        "ix_shipment_status_transition_source", table_name="shipment_status_transition"
    )
    op.drop_table("shipment_status_transition")
    op.drop_table("shipment_status")
