"""Request/response models for the shipment endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class TransitionOption(BaseModel):
    """A legal next step for a specific shipment, straight from the graph."""

    # Target status code this option would move the shipment into.
    target: str
    # Lifecycle event name to send when choosing this option.
    event: str
    # Button / menu label shown in the UI.
    label: str
    # Short hint for the operator (often empty).
    description: str = ""
    # When True, the client must supply a non-empty `reason` on the status POST.
    requires_reason: bool = False


class ShipmentEventRead(BaseModel):
    """One append-only audit row from `shipment_event`."""

    model_config = ConfigDict(from_attributes=True)

    # Monotonic primary key; also usable as a history pagination cursor.
    id: int
    # Status before the change; NULL means the shipment was created in `target_status`.
    source_status: str | None
    # Status after this event applied.
    target_status: str
    # Lifecycle event that caused the change (or "seed" / "create" on insert).
    event: str
    # Free-text justification; required by the `require_reason` guard on fail.
    reason: str | None
    # Who triggered the change (user id, service name, or "system").
    actor: str
    # Wall-clock time of the transition.
    occurred_at: datetime


class ShipmentRead(BaseModel):
    """Shipment row plus UI-ready transition hints."""

    model_config = ConfigDict(from_attributes=True)

    # Surrogate primary key (UUID).
    id: uuid.UUID
    # External tracking number / booking id; unique and shown in the UI.
    reference: str
    # Recipient / booking customer display name.
    customer_name: str
    # Current lifecycle state code (FK to `shipment_status.code`).
    status: str
    # Optimistic-lock counter; bumped on every status change.
    version: int
    # When `status` last changed (not the same as updated_at if other fields move).
    status_changed_at: datetime
    # Row creation time.
    created_at: datetime
    # Last time any column on the shipment row was updated.
    updated_at: datetime
    # Precomputed so the UI never has to reimplement the transition rules.
    allowed_transitions: list[TransitionOption] = Field(default_factory=list)
    # True when `status` is a terminal lifecycle state (no further moves).
    is_terminal: bool = False
    # Most recent audit event, if any; handy for the list/detail header.
    last_event: ShipmentEventRead | None = None


class StatusUpdateRequest(BaseModel):
    """Body of `POST /shipments/{id}/status`."""

    # Target status code the client wants to move into.
    status: str = Field(description="Target status code.")
    # Free-text note; required by transitions guarded with require_reason.
    reason: str | None = Field(
        default=None,
        max_length=500,
        description="Free-text note; required by transitions guarded with require_reason.",
    )
    # Who performed the change (defaults to the web UI identity).
    actor: str = Field(
        default="web-ui", max_length=120, description="Who performed the change."
    )
    # Client's known `version`; mismatch → 409 instead of overwriting a newer change.
    expected_version: int | None = Field(
        default=None,
        ge=1,
        description=(
            "Version the client believes it is updating. When supplied, a "
            "mismatch is rejected with 409 instead of overwriting a newer change."
        ),
    )

    @field_validator("status")
    @classmethod
    def _normalise_status(cls, value: str) -> str:
        return value.strip().lower()

    @field_validator("reason")
    @classmethod
    def _blank_to_none(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


class StatusUpdateResponse(BaseModel):
    """Result of a successful status transition."""

    # Shipment after the update (includes refreshed allowed_transitions).
    shipment: ShipmentRead
    # The audit row just appended for this transition.
    event: ShipmentEventRead


class StatusCount(BaseModel):
    """One bucket in the summary histogram."""

    # Lifecycle status code for this bucket.
    status: str
    # Number of shipments currently in this status.
    count: int


class ShipmentSummary(BaseModel):
    """Counts per status for the whole collection, independent of the page."""

    # Total shipments across all statuses.
    total: int
    # Per-status breakdown (same codes as the lifecycle graph).
    by_status: list[StatusCount]
