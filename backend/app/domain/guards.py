"""Guard registry for the state machine.

A guard is a named predicate a transition can opt into from configuration
(`guards: [require_reason]`). Keeping them in a registry means the config stays
declarative while the conditions themselves remain testable Python.

Adding a rule is a two-line change here plus one line of YAML; the engine and
the service layer are untouched.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TransitionContext:
    """Everything a guard is allowed to look at when judging a transition."""

    source: str
    target: str
    event: str
    reason: str | None = None
    actor: str | None = None
    metadata: Mapping[str, object] | None = None


@dataclass(frozen=True, slots=True)
class GuardResult:
    allowed: bool
    message: str | None = None

    @classmethod
    def ok(cls) -> GuardResult:
        return cls(True)

    @classmethod
    def reject(cls, message: str) -> GuardResult:
        return cls(False, message)


Guard = Callable[[TransitionContext], GuardResult]

_REGISTRY: dict[str, Guard] = {}


def register_guard(name: str) -> Callable[[Guard], Guard]:
    def decorator(fn: Guard) -> Guard:
        if name in _REGISTRY:
            raise ValueError(f"guard {name!r} is already registered")
        _REGISTRY[name] = fn
        return fn

    return decorator


def resolve_guard(name: str) -> Guard:
    try:
        return _REGISTRY[name]
    except KeyError:
        known = ", ".join(sorted(_REGISTRY)) or "<none>"
        raise KeyError(f"unknown guard {name!r}; registered guards: {known}") from None


def registered_guards() -> tuple[str, ...]:
    return tuple(sorted(_REGISTRY))


@register_guard("require_reason")
def _require_reason(ctx: TransitionContext) -> GuardResult:
    if ctx.reason and ctx.reason.strip():
        return GuardResult.ok()
    return GuardResult.reject(
        f"A reason is required when moving a shipment to '{ctx.target}'."
    )
