"""Strategy registry: evidence is bound to strategy_id + config hash + dataset hash (ADR-0021)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from xau_edge.experiments.registry import ExperimentRegistry
from xau_edge.signals.evidence import PERIODS, evidence_for_strategy
from xau_edge.signals.schema import EvidenceStatus
from xau_edge.signals.strategy_registry import (
    StrategyRegistry,
    StrategySpec,
    config_hash,
    dataset_hash,
    default_strategy,
)

PARAMS = {"strategy": "h_demo", "window": 3}


def _spec(params: dict[str, Any] | None = None) -> StrategySpec:
    return StrategySpec(strategy_id="h_demo", family="edge", params=params or PARAMS)


def _rec(
    reg: ExperimentRegistry,
    period: str,
    passed: bool,
    *,
    params: dict[str, Any] | None = None,
    datasets: dict[str, str] | None = None,
    family: str = "edge",
) -> None:
    reg.record(
        family=family,
        name=f"{family}-{period}",
        dataset_ids=datasets or {"H1": "d1"},
        feature_ids={},
        params=params or PARAMS,
        seeds={},
        period=period,
        metrics={"verdict": {"passed": passed}} if family == "backtest" else {"passed": passed},
        code_version="x",
        code_dirty=False,
    )


def _all_pass(reg: ExperimentRegistry, **kwargs: Any) -> None:
    for p in PERIODS:
        _rec(reg, p, True, **kwargs)


def test_hashes_are_stable_and_order_independent() -> None:
    assert config_hash({"a": 1, "b": 2}) == config_hash({"b": 2, "a": 1})
    assert config_hash({"a": 1}) != config_hash({"a": 2})
    assert dataset_hash({"H1": "x", "M15": "y"}) == dataset_hash({"M15": "y", "H1": "x"})
    assert dataset_hash({"H1": "x"}) != dataset_hash({"H1": "z"})


def test_default_strategy_is_baseline_c_and_registry_lookup() -> None:
    spec = default_strategy()
    assert spec.strategy_id == "baseline_c"
    reg = StrategyRegistry()
    reg.register(spec)
    assert reg.get("baseline_c") is spec
    assert reg.ids() == ("baseline_c",)
    with pytest.raises(KeyError):
        reg.get("nope")
    with pytest.raises(ValueError, match="already"):
        reg.register(spec)


def test_validated_only_with_three_matching_passes(tmp_path: Path) -> None:
    reg = ExperimentRegistry(tmp_path)
    assert evidence_for_strategy(reg, _spec()) is EvidenceStatus.NONE
    _rec(reg, "development", True)
    _rec(reg, "validation", True)
    assert evidence_for_strategy(reg, _spec()) is EvidenceStatus.NONE
    _rec(reg, "test", True)
    assert evidence_for_strategy(reg, _spec()) is EvidenceStatus.VALIDATED


def test_changed_config_does_not_inherit_evidence(tmp_path: Path) -> None:
    reg = ExperimentRegistry(tmp_path)
    _all_pass(reg)
    other = {"strategy": "h_demo", "window": 4}
    assert evidence_for_strategy(reg, _spec(other)) is EvidenceStatus.NONE


def test_other_strategy_id_with_same_numbers_does_not_count(tmp_path: Path) -> None:
    reg = ExperimentRegistry(tmp_path)
    _all_pass(reg, params={"strategy": "h_other", "window": 3})
    assert evidence_for_strategy(reg, _spec()) is EvidenceStatus.NONE


def test_dataset_hash_must_match_when_required(tmp_path: Path) -> None:
    reg = ExperimentRegistry(tmp_path)
    _all_pass(reg, datasets={"H1": "d1"})
    good = dataset_hash({"H1": "d1"})
    assert evidence_for_strategy(reg, _spec(), dataset=good) is EvidenceStatus.VALIDATED
    wrong = dataset_hash({"H1": "d2"})
    assert evidence_for_strategy(reg, _spec(), dataset=wrong) is EvidenceStatus.NONE


def test_periods_on_different_datasets_do_not_add_up(tmp_path: Path) -> None:
    reg = ExperimentRegistry(tmp_path)
    _rec(reg, "development", True, datasets={"H1": "old"})
    _rec(reg, "validation", True)
    _rec(reg, "test", True)
    assert evidence_for_strategy(reg, _spec()) is EvidenceStatus.NONE


def test_a_later_failure_revokes(tmp_path: Path) -> None:
    reg = ExperimentRegistry(tmp_path)
    _all_pass(reg)
    _rec(reg, "validation", False)
    assert evidence_for_strategy(reg, _spec()) is EvidenceStatus.NONE


def test_backtest_family_uses_verdict_shape(tmp_path: Path) -> None:
    reg = ExperimentRegistry(tmp_path)
    spec = StrategySpec(strategy_id="h_demo", family="backtest", params=PARAMS)
    for p in PERIODS:
        _rec(reg, p, True, family="backtest")
    assert evidence_for_strategy(reg, spec) is EvidenceStatus.VALIDATED


def test_default_strategy_without_records_is_none(tmp_path: Path) -> None:
    reg = ExperimentRegistry(tmp_path)
    assert evidence_for_strategy(reg, default_strategy()) is EvidenceStatus.NONE
