"""Loads the shipment state graph from its YAML definition.

The machine is immutable and process-wide, so it is built once and cached.
`load_state_machine.cache_clear()` gives tests a clean slate.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml

from app.core.config import get_settings
from app.domain.errors import LifecycleConfigError
from app.domain.state_machine import StateMachine


def load_state_machine_from_path(path: Path) -> StateMachine:
    if not path.exists():
        raise LifecycleConfigError(f"Lifecycle config not found at {path}.")
    try:
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise LifecycleConfigError(f"Lifecycle config at {path} is not valid YAML: {exc}") from exc
    return StateMachine.from_config(document)


@lru_cache(maxsize=1)
def load_state_machine() -> StateMachine:
    return load_state_machine_from_path(get_settings().lifecycle_config_path)


def get_shipment_lifecycle() -> StateMachine:
    """FastAPI dependency handing out the shared shipment state machine."""
    return load_state_machine()
