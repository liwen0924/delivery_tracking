"""Domain-level errors.

These are transport agnostic on purpose: the service layer raises them, and a
single translation layer in `app.api.errors` maps them onto HTTP responses.
"""

from __future__ import annotations

from typing import Any


class DomainError(Exception):
    """Base class for every expected (non-bug) failure in the domain."""

    code: str = "domain_error"
    http_status: int = 400

    def __init__(self, message: str, **details: Any) -> None:
        super().__init__(message)
        self.message = message
        self.details: dict[str, Any] = details


class LifecycleConfigError(DomainError):
    """The lifecycle configuration file is malformed or inconsistent."""

    code = "lifecycle_config_invalid"
    http_status = 500


class UnknownStateError(DomainError):
    """A state code was referenced that does not exist in the state graph."""

    code = "unknown_state"
    http_status = 422


class InvalidTransitionError(DomainError):
    """The requested transition is not an edge of the state graph."""

    code = "invalid_transition"
    http_status = 409


class GuardRejectedError(DomainError):
    """The transition edge exists but one of its guards refused it."""

    code = "transition_guard_rejected"
    http_status = 422


class ShipmentNotFoundError(DomainError):
    code = "shipment_not_found"
    http_status = 404


class ConcurrentUpdateError(DomainError):
    """Optimistic-locking clash: the shipment moved on since it was read."""

    code = "concurrent_update"
    http_status = 409
