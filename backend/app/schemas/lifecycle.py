"""Response models describing the state graph itself.

The UI fetches this once and renders its status chips, filter list and action
menus from it — so a change to `shipment_lifecycle.yaml` reaches the browser
without touching frontend code either.
"""

from __future__ import annotations

from pydantic import BaseModel


class LifecycleState(BaseModel):
    code: str
    label: str
    description: str
    initial: bool
    terminal: bool
    tone: str
    position: int
    allowed_targets: list[str]


class LifecycleTransition(BaseModel):
    event: str
    label: str
    source: str
    target: str
    description: str
    guards: list[str]


class LifecycleRead(BaseModel):
    name: str
    version: int
    initial_state: str
    states: list[LifecycleState]
    transitions: list[LifecycleTransition]
