"""Response models describing the state graph itself.

The UI fetches this once and renders its status chips, filter list and action
menus from it — so a change to `shipment_lifecycle.yaml` reaches the browser
without touching frontend code either.
"""

from __future__ import annotations

from pydantic import BaseModel


class LifecycleState(BaseModel):
    """One node in the lifecycle graph (mirrors `shipment_status` + YAML)."""

    # Machine-readable key, e.g. "created" / "in_transit"; matches DB `code`.
    code: str
    # Human-readable name shown on chips and filters, e.g. "In transit".
    label: str
    # Longer explanation of what this state means operationally.
    description: str
    # True for the single entry state new shipments start in.
    initial: bool
    # True when no further transitions are allowed (e.g. delivered, failed).
    terminal: bool
    # UI badge colour hint: neutral | info | progress | success | danger.
    tone: str
    # Display order when listing states (matches YAML declaration order).
    position: int
    # Status codes reachable in one hop from this state (derived from edges).
    allowed_targets: list[str]


class LifecycleTransition(BaseModel):
    """One legal edge of the lifecycle graph (mirrors `shipment_status_transition`)."""

    # Machine-readable event name the client sends, e.g. "pick_up" / "fail".
    event: str
    # Button / menu label shown in the UI, e.g. "Mark picked up".
    label: str
    # Status the shipment must currently be in for this edge to apply.
    source: str
    # Status the shipment moves to when this transition fires.
    target: str
    # Operator-facing notes (guards, caveats) for this edge.
    description: str
    # Guard names that must pass, e.g. ["require_reason"] for fail paths.
    guards: list[str]


class LifecycleRead(BaseModel):
    """Full graph payload for `GET /lifecycle`."""

    # Graph identifier from YAML (e.g. "shipment").
    name: str
    # Schema version from YAML; bump when the graph shape changes.
    version: int
    # Status code of the entry state (same as the state with `initial=True`).
    initial_state: str
    # All nodes, ordered by `position`.
    states: list[LifecycleState]
    # All legal edges; UI builds action menus from these + per-shipment options.
    transitions: list[LifecycleTransition]
