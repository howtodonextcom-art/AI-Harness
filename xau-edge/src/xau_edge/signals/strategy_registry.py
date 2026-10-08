"""Strategy registry (ADR-0021): which strategies the signal layer knows and how to identify them.

A strategy is identified by ``strategy_id`` plus the hash of its exact configuration; the evidence
gate looks validation records up by that identity and by the hash of the datasets they ran on.
The registry never grants evidence itself: it only names strategies. With no strategy holding a
VALIDATED record the decision layer keeps answering WAIT.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def config_hash(params: Mapping[str, Any]) -> str:
    """Stable 16-hex hash of a strategy configuration (key order does not matter)."""
    return hashlib.sha256(_canonical(dict(params)).encode()).hexdigest()[:16]


def dataset_hash(dataset_ids: Mapping[str, str]) -> str:
    """Stable 16-hex hash of the ``{timeframe: dataset_id}`` mapping a run used."""
    return hashlib.sha256(_canonical(dict(dataset_ids)).encode()).hexdigest()[:16]


@dataclass(frozen=True)
class StrategySpec:
    """Identity of a strategy for the evidence gate: id, experiment family and exact params."""

    strategy_id: str
    family: str
    params: Mapping[str, Any] = field(default_factory=dict)

    @property
    def config_hash(self) -> str:
        """Hash of ``params``; any change in configuration is a different identity."""
        return config_hash(self.params)


class StrategyRegistry:
    """Named strategies known to the signal layer."""

    def __init__(self) -> None:
        self._specs: dict[str, StrategySpec] = {}

    def register(self, spec: StrategySpec) -> None:
        """Add a strategy; ids are unique."""
        if spec.strategy_id in self._specs:
            msg = f"strategy {spec.strategy_id!r} is already registered"
            raise ValueError(msg)
        self._specs[spec.strategy_id] = spec

    def get(self, strategy_id: str) -> StrategySpec:
        """The spec for ``strategy_id`` (KeyError if unknown)."""
        return self._specs[strategy_id]

    def ids(self) -> tuple[str, ...]:
        """Registered ids, sorted."""
        return tuple(sorted(self._specs))


def default_strategy() -> StrategySpec:
    """Baseline C (analogues only), the strategy the signal engine's inputs mirror today."""
    from xau_edge.evaluation.runner import strategy_params  # noqa: PLC0415 - avoids import cycle

    return StrategySpec("baseline_c", "backtest", strategy_params("baseline_c"))
