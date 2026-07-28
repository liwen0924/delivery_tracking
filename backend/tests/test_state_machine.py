"""Unit tests for the transition rules — no database, no HTTP.

The lifecycle is loaded from the real config file, so these tests also protect
`config/shipment_lifecycle.yaml` from being edited into an invalid graph.
"""

from __future__ import annotations

import pytest

from app.domain.errors import (
    GuardRejectedError,
    InvalidTransitionError,
    LifecycleConfigError,
    UnknownStateError,
)
from app.domain.state_machine import StateMachine

ALL_STATUSES = [
    "created",
    "picked_up",
    "in_transit",
    "intercepted",
    "delivered",
    "returned",
    "canceled",
    "failed",
]

# The full adjacency matrix:
#   created -> picked_up -> in_transit -> delivered
#   created -> canceled
#   picked_up -> intercepted -> returned
#   failed reachable from every non-terminal status
LEGAL_EDGES = {
    ("created", "picked_up"),
    ("created", "canceled"),
    ("created", "failed"),
    ("picked_up", "in_transit"),
    ("picked_up", "intercepted"),
    ("picked_up", "failed"),
    ("in_transit", "delivered"),
    ("in_transit", "failed"),
    ("intercepted", "returned"),
    ("intercepted", "failed"),
}


@pytest.mark.parametrize("source", ALL_STATUSES)
@pytest.mark.parametrize("target", ALL_STATUSES)
def test_transition_matrix_matches_the_brief(lifecycle, source, target):
    """Every source/target pair is allowed exactly when it should be."""
    assert lifecycle.can(source, target) is ((source, target) in LEGAL_EDGES)


def test_happy_path_is_walkable(lifecycle):
    status = lifecycle.initial_state.code
    assert status == "created"
    for target in ("picked_up", "in_transit", "delivered"):
        transition = lifecycle.validate(status, target)
        assert transition.target == target
        status = target
    assert lifecycle.is_terminal(status)


def test_skipping_a_step_is_rejected_with_a_useful_message(lifecycle):
    with pytest.raises(InvalidTransitionError) as excinfo:
        lifecycle.validate("created", "delivered")

    error = excinfo.value
    assert "created" in error.message and "delivered" in error.message
    # The error tells the caller what *would* have worked.
    assert set(error.details["allowed_targets"]) == {"picked_up", "canceled", "failed"}


def test_backwards_transitions_are_rejected(lifecycle):
    with pytest.raises(InvalidTransitionError):
        lifecycle.validate("in_transit", "picked_up")


@pytest.mark.parametrize("terminal", ["delivered", "returned", "canceled", "failed"])
def test_terminal_states_have_no_way_out(lifecycle, terminal):
    assert lifecycle.is_terminal(terminal)
    assert lifecycle.allowed_transitions(terminal) == ()
    with pytest.raises(InvalidTransitionError) as excinfo:
        lifecycle.validate(terminal, "in_transit")
    assert excinfo.value.details["terminal"] is True


def test_intercept_path_is_walkable(lifecycle):
    transition = lifecycle.validate("picked_up", "intercepted")
    assert transition.event == "intercept"
    transition = lifecycle.validate("intercepted", "returned")
    assert transition.event == "return"
    assert lifecycle.is_terminal("returned")


def test_only_picked_up_can_enter_intercepted(lifecycle):
    for source in ALL_STATUSES:
        if source == "picked_up":
            continue
        assert not lifecycle.can(source, "intercepted")


def test_only_intercepted_can_enter_returned(lifecycle):
    for source in ALL_STATUSES:
        if source == "intercepted":
            continue
        assert not lifecycle.can(source, "returned")


def test_created_can_be_canceled(lifecycle):
    assert lifecycle.validate("created", "canceled").event == "cancel"
    assert lifecycle.is_terminal("canceled")


def test_delivered_cannot_be_failed(lifecycle):
    """The `except:` list in the config is what stops this."""
    assert not lifecycle.can("delivered", "failed")


@pytest.mark.parametrize("source", ["created", "picked_up", "in_transit", "intercepted"])
def test_failure_is_reachable_from_every_non_terminal_state(lifecycle, source):
    assert lifecycle.validate(source, "failed", reason="Address not found").event == "fail"


@pytest.mark.parametrize("reason", [None, "", "   "])
def test_failing_without_a_reason_is_blocked_by_the_guard(lifecycle, reason):
    with pytest.raises(GuardRejectedError) as excinfo:
        lifecycle.validate("in_transit", "failed", reason=reason)
    assert excinfo.value.details["guard"] == "require_reason"


def test_unknown_states_are_reported_separately_from_illegal_moves(lifecycle):
    with pytest.raises(UnknownStateError):
        lifecycle.validate("created", "teleported")
    with pytest.raises(UnknownStateError):
        lifecycle.validate("nowhere", "created")


def test_allowed_transitions_expose_labels_for_the_ui(lifecycle):
    options = {t.target: t for t in lifecycle.allowed_transitions("created")}
    assert options["picked_up"].label == "Mark picked up"
    assert options["failed"].guard_names == ("require_reason",)


def test_graph_is_serialisable_for_the_api(lifecycle):
    graph = lifecycle.to_graph()
    assert graph["initial_state"] == "created"
    assert {s["code"] for s in graph["states"]} == set(ALL_STATUSES)
    assert len(graph["transitions"]) == len(LEGAL_EDGES)


# ---------------------------------------------------------------------------
# The engine is generic: a different config yields a different machine with no
# code change. These cases guard that promise.
# ---------------------------------------------------------------------------


def _machine(**overrides) -> StateMachine:
    config = {
        "name": "test",
        "version": 1,
        "states": [
            {"code": "draft", "initial": True},
            {"code": "live"},
            {"code": "archived", "terminal": True},
        ],
        "transitions": [
            {"event": "publish", "from": "draft", "to": "live"},
            {"event": "archive", "from": "*", "except": ["archived"], "to": "archived"},
        ],
    }
    config.update(overrides)
    return StateMachine.from_config(config)


def test_a_different_config_produces_a_different_machine():
    machine = _machine()
    assert machine.initial_state.code == "draft"
    assert set(machine.allowed_targets("draft")) == {"live", "archived"}
    assert machine.allowed_targets("archived") == ()


def test_wildcard_expands_to_every_state_except_the_exclusions():
    machine = _machine()
    archiving = {t.source for t in machine.transitions if t.target == "archived"}
    assert archiving == {"draft", "live"}


@pytest.mark.parametrize(
    ("overrides", "expected"),
    [
        (
            {
                "states": [{"code": "a", "initial": True}, {"code": "b", "initial": True}],
                "transitions": [],
            },
            "initial",
        ),
        ({"states": [{"code": "a"}, {"code": "b"}], "transitions": []}, "initial"),
        ({"states": [{"code": "a", "initial": True}, {"code": "a"}]}, "Duplicate state"),
        ({"transitions": [{"event": "go", "from": "draft", "to": "ghost"}]}, "unknown state"),
        ({"transitions": [{"event": "go", "from": "ghost", "to": "live"}]}, "unknown state"),
        (
            {"transitions": [{"event": "go", "from": "draft", "to": "live", "guards": ["x"]}]},
            "guard",
        ),
        (
            {
                "transitions": [
                    {"event": "go", "from": "draft", "to": "live"},
                    {"event": "again", "from": "draft", "to": "live"},
                ]
            },
            "Duplicate transition",
        ),
    ],
)
def test_invalid_configuration_fails_loudly_at_load_time(overrides, expected):
    with pytest.raises(LifecycleConfigError) as excinfo:
        _machine(**overrides)
    assert expected.lower() in str(excinfo.value).lower()
