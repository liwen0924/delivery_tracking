"""Request/response models for the shipment endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class TransitionOption(BaseModel):
    """A legal next step for a specific shipment, straight from the graph."""

    target: str
    event: str
    label: str
    description: str = ""
    requires_reason: bool = False


class ShipmentEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    source_status: str | None
    target_status: str
    event: str
    reason: str | None
    actor: str
    occurred_at: datetime


class ShipmentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    reference: str
    customer_name: str
    status: str
    version: int
    status_changed_at: datetime
    created_at: datetime
    updated_at: datetime
    # Precomputed so the UI never has to reimplement the transition rules.
    allowed_transitions: list[TransitionOption] = Field(default_factory=list)
    is_terminal: bool = False
    last_event: ShipmentEventRead | None = None


class StatusUpdateRequest(BaseModel):
    """Body of `POST /shipments/{id}/status`."""

    status: str = Field(description="Target status code.")
    reason: str | None = Field(
        default=None,
        max_length=500,
        description="Free-text note; required by transitions guarded with require_reason.",
    )
    actor: str = Field(
        default="web-ui", max_length=120, description="Who performed the change."
    )
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
    shipment: ShipmentRead
    event: ShipmentEventRead


class StatusCount(BaseModel):
    status: str
    count: int


class ShipmentSummary(BaseModel):
    """Counts per status for the whole collection, independent of the page."""

    total: int
    by_status: list[StatusCount]
