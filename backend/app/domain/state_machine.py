"""A small, generic, configuration-driven finite state machine.

The engine knows nothing about shipments. It is handed a parsed transition
table (states + edges) and answers three questions:

    * which states exist, and which are initial/terminal?
    * which transitions are legal from a given state?
    * is *this* transition legal right now, and do its guards agree?

Nothing here needs to change when the state graph does — that lives in
`config/shipment_lifecycle.yaml`.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any

from app.domain.errors import (
    GuardRejectedError,
    InvalidTransitionError,
    LifecycleConfigError,
    UnknownStateError,
)
from app.domain.guards import Guard, TransitionContext, resolve_guard

WILDCARD = "*"


@dataclass(frozen=True, slots=True)
class State:
    code: str
    label: str
    description: str = ""
    initial: bool = False
    terminal: bool = False
    tone: str = "neutral"
    position: int = 0


@dataclass(frozen=True, slots=True)
class Transition:
    event: str
    label: str
    source: str
    target: str
    description: str = ""
    guard_names: tuple[str, ...] = ()
    guards: tuple[Guard, ...] = field(default=(), repr=False, compare=False)

    def check_guards(self, ctx: TransitionContext) -> None:
        for name, guard in zip(self.guard_names, self.guards, strict=True):
            result = guard(ctx)
            if not result.allowed:
                raise GuardRejectedError(
                    result.message or f"Transition rejected by guard '{name}'.",
                    guard=name,
                    source=self.source,
                    target=self.target,
                    event=self.event,
                )


class StateMachine:
    """Immutable state graph built from a declarative transition table."""

    def __init__(
        self,
        *,
        name: str,
        version: int,
        states: Sequence[State],
        transitions: Sequence[Transition],
    ) -> None:
        self.name = name
        self.version = version

        self._states: Mapping[str, State] = MappingProxyType(
            {state.code: state for state in states}
        )
        self._transitions: tuple[Transition, ...] = tuple(transitions)

        outgoing: dict[str, list[Transition]] = {code: [] for code in self._states}
        by_pair: dict[tuple[str, str], Transition] = {}
        for transition in self._transitions:
            outgoing[transition.source].append(transition)
            by_pair[(transition.source, transition.target)] = transition
        self._outgoing: Mapping[str, tuple[Transition, ...]] = MappingProxyType(
            {code: tuple(items) for code, items in outgoing.items()}
        )
        self._by_pair: Mapping[tuple[str, str], Transition] = MappingProxyType(by_pair)

        initial = [state for state in states if state.initial]
        if len(initial) != 1:
            raise LifecycleConfigError(
                "Exactly one state must be marked as initial, "
                f"found {len(initial)}: {[s.code for s in initial]}"
            )
        self._initial: State = initial[0]

    # ---------------------------------------------------------------- states

    @property
    def states(self) -> tuple[State, ...]:
        return tuple(self._states.values())

    @property
    def transitions(self) -> tuple[Transition, ...]:
        return self._transitions

    @property
    def initial_state(self) -> State:
        return self._initial

    def has_state(self, code: str) -> bool:
        return code in self._states

    def state(self, code: str) -> State:
        try:
            return self._states[code]
        except KeyError:
            raise UnknownStateError(
                f"Unknown status '{code}'.",
                status=code,
                known_statuses=list(self._states),
            ) from None

    def is_terminal(self, code: str) -> bool:
        return self.state(code).terminal

    # ----------------------------------------------------------- transitions

    def allowed_transitions(self, source: str) -> tuple[Transition, ...]:
        self.state(source)  # validates the source exists
        return self._outgoing.get(source, ())

    def allowed_targets(self, source: str) -> tuple[str, ...]:
        return tuple(t.target for t in self.allowed_transitions(source))

    def can(self, source: str, target: str) -> bool:
        return (source, target) in self._by_pair

    def validate(
        self,
        source: str,
        target: str,
        *,
        reason: str | None = None,
        actor: str | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> Transition:
        """Return the transition for source -> target or raise.

        Raises `UnknownStateError` for states outside the graph,
        `InvalidTransitionError` for edges that do not exist, and
        `GuardRejectedError` when an edge exists but its guards refuse.
        """
        self.state(source)
        self.state(target)

        transition = self._by_pair.get((source, target))
        if transition is None:
            allowed = self.allowed_targets(source)
            hint = ", ".join(allowed) if allowed else "none (terminal status)"
            raise InvalidTransitionError(
                f"Cannot move shipment from '{source}' to '{target}'. "
                f"Allowed next statuses: {hint}.",
                source=source,
                target=target,
                allowed_targets=list(allowed),
                terminal=self.is_terminal(source),
            )

        transition.check_guards(
            TransitionContext(
                source=source,
                target=target,
                event=transition.event,
                reason=reason,
                actor=actor,
                metadata=metadata,
            )
        )
        return transition

    # ---------------------------------------------------------------- config

    @classmethod
    def from_config(cls, config: Mapping[str, Any]) -> StateMachine:
        """Build a machine from the parsed lifecycle document."""
        return _build(config)

    def to_graph(self) -> dict[str, Any]:
        """Serialisable view of the graph, consumed by the API and the UI."""
        return {
            "name": self.name,
            "version": self.version,
            "initial_state": self._initial.code,
            "states": [
                {
                    "code": s.code,
                    "label": s.label,
                    "description": s.description,
                    "initial": s.initial,
                    "terminal": s.terminal,
                    "tone": s.tone,
                    "position": s.position,
                    "allowed_targets": list(self.allowed_targets(s.code)),
                }
                for s in self.states
            ],
            "transitions": [
                {
                    "event": t.event,
                    "label": t.label,
                    "source": t.source,
                    "target": t.target,
                    "description": t.description,
                    "guards": list(t.guard_names),
                }
                for t in self._transitions
            ],
        }


# --------------------------------------------------------------------------
# Config parsing
# --------------------------------------------------------------------------


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return list(value)
    return [value]


def _build(config: Mapping[str, Any]) -> StateMachine:
    if not isinstance(config, Mapping):
        raise LifecycleConfigError("Lifecycle config must be a mapping.")

    raw_states = config.get("states")
    if not raw_states:
        raise LifecycleConfigError("Lifecycle config must define at least one state.")

    states: list[State] = []
    seen: set[str] = set()
    for position, raw in enumerate(raw_states):
        code = str(raw.get("code", "")).strip()
        if not code:
            raise LifecycleConfigError(f"State #{position} is missing a 'code'.")
        if code == WILDCARD:
            raise LifecycleConfigError(f"'{WILDCARD}' is reserved and cannot be a state code.")
        if code in seen:
            raise LifecycleConfigError(f"Duplicate state code '{code}'.")
        seen.add(code)
        states.append(
            State(
                code=code,
                label=str(raw.get("label", code.replace("_", " ").title())),
                description=str(raw.get("description", "")),
                initial=bool(raw.get("initial", False)),
                terminal=bool(raw.get("terminal", False)),
                tone=str(raw.get("tone", "neutral")),
                position=position,
            )
        )

    transitions = _expand_transitions(config.get("transitions") or [], seen)

    return StateMachine(
        name=str(config.get("name", "state_machine")),
        version=int(config.get("version", 1)),
        states=states,
        transitions=transitions,
    )


def _expand_transitions(
    raw_transitions: Iterable[Mapping[str, Any]], known_states: set[str]
) -> list[Transition]:
    expanded: list[Transition] = []
    pairs: set[tuple[str, str]] = set()

    for index, raw in enumerate(raw_transitions):
        event = str(raw.get("event", "")).strip()
        if not event:
            raise LifecycleConfigError(f"Transition #{index} is missing an 'event'.")

        target = str(raw.get("to", "")).strip()
        if target not in known_states:
            raise LifecycleConfigError(
                f"Transition '{event}' targets unknown state '{target}'."
            )

        excluded = {str(code) for code in _as_list(raw.get("except"))}
        unknown_excluded = excluded - known_states
        if unknown_excluded:
            raise LifecycleConfigError(
                f"Transition '{event}' excludes unknown state(s): "
                f"{sorted(unknown_excluded)}."
            )

        sources = _resolve_sources(event, raw.get("from"), known_states, excluded)

        guard_names = tuple(str(g) for g in _as_list(raw.get("guards")))
        try:
            guards = tuple(resolve_guard(name) for name in guard_names)
        except KeyError as exc:
            raise LifecycleConfigError(
                f"Transition '{event}' references an unknown guard: {exc}"
            ) from None

        for source in sources:
            if (source, target) in pairs:
                raise LifecycleConfigError(
                    f"Duplicate transition '{source}' -> '{target}' "
                    f"(second definition came from event '{event}')."
                )
            pairs.add((source, target))
            expanded.append(
                Transition(
                    event=event,
                    label=str(raw.get("label", event.replace("_", " ").capitalize())),
                    source=source,
                    target=target,
                    description=str(raw.get("description", "")),
                    guard_names=guard_names,
                    guards=guards,
                )
            )

    return expanded


def _resolve_sources(
    event: str,
    raw_from: Any,
    known_states: set[str],
    excluded: set[str],
) -> list[str]:
    """Expand `from` — which may be a wildcard, a single code, or a list."""
    declared = _as_list(raw_from)
    if not declared:
        raise LifecycleConfigError(f"Transition '{event}' is missing 'from'.")

    if WILDCARD in {str(item) for item in declared}:
        if len(declared) > 1:
            raise LifecycleConfigError(
                f"Transition '{event}' mixes the '{WILDCARD}' wildcard with "
                "explicit source states; use 'except' instead."
            )
        # Deterministic order keeps the generated transition table stable.
        return [code for code in sorted(known_states) if code not in excluded]

    sources = [str(item) for item in declared]
    unknown = set(sources) - known_states
    if unknown:
        raise LifecycleConfigError(
            f"Transition '{event}' starts from unknown state(s): {sorted(unknown)}."
        )
    return [code for code in sources if code not in excluded]
