"""Expected value after costs, and the evidence gate backed by the experiment registry."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from xau_edge.experiments.registry import ExperimentRegistry
from xau_edge.outcomes.summary import OutcomeSummary
from xau_edge.signals.evidence import evidence_status
from xau_edge.signals.expected_value import analogue_expected_r, cost_in_r, expected_r
from xau_edge.signals.schema import EvidenceStatus


def test_cost_in_r_hand_value_and_validation() -> None:
    # (30 spread + 2 x 3 slippage) points x 0.01 = 0.36 price units over a 7.5 stop = 0.048 R
    assert cost_in_r(30, 3, 7.5) == pytest.approx(0.048)
    assert cost_in_r(0, 0, 1.0) == 0.0
    with pytest.raises(ValueError, match="stop_distance"):
        cost_in_r(30, 3, 0.0)
    with pytest.raises(ValueError, match="spread_points"):
        cost_in_r(float("nan"), 3, 5.0)


def test_expected_r_follows_the_briefs_formula() -> None:
    assert expected_r(0.4, 2.0, 0.6, 1.0, 0.05) == pytest.approx(0.4 * 2 - 0.6 * 1 - 0.05)
    assert expected_r(0.5, 1.0, 0.5, 1.0, 0.0) == pytest.approx(0.0)
    with pytest.raises(ValueError, match="probabilities"):
        expected_r(0.7, 1.0, 0.5, 1.0, 0.0)


def test_negative_ev_is_reported_as_negative() -> None:
    assert expected_r(0.3, 2.0, 0.7, 1.0, 0.05) < 0  # a 2:1 payoff needs more than 33% wins


def _summary(long_r: float, short_r: float) -> OutcomeSummary:
    return OutcomeSummary(
        n=20,
        p_up=0.5,
        p_down=0.3,
        p_neutral=0.2,
        p_up_ci=(0.3, 0.7),
        p_down_ci=(0.1, 0.5),
        mean_forward_atr=0.2,
        median_forward_atr=0.1,
        mean_return=0.001,
        percentiles={5: -1.0, 25: -0.3, 50: 0.1, 75: 0.5, 95: 1.2},
        mean_max_up_atr=1.0,
        mean_max_down_atr=0.8,
        expected_r_long=long_r,
        expected_r_short=short_r,
    )


def test_analogue_ev_subtracts_friction_for_the_chosen_side() -> None:
    s = _summary(0.30, -0.10)
    assert analogue_expected_r(s, +1, 0.05) == pytest.approx(0.25)
    assert analogue_expected_r(s, -1, 0.05) == pytest.approx(-0.15)


def _rec(
    reg: ExperimentRegistry,
    family: str,
    period: str,
    passed: bool,
    params: dict[str, Any],
    *,
    datasets: dict[str, str] | None = None,
    dirty: bool = False,
) -> None:
    metrics: dict[str, Any] = (
        {"verdict": {"passed": passed}} if family == "backtest" else {"passed": passed}
    )
    reg.record(
        family=family,
        name=f"{family}-{period}",
        dataset_ids=datasets or {"M15": "d1"},
        feature_ids={},
        params=params,
        seeds={},
        period=period,
        metrics=metrics,
        code_version="x",
        code_dirty=dirty,
    )


A = {"strategy": "a"}


def _gate(reg: ExperimentRegistry, family: str = "backtest", params: dict[str, Any] | None = None):  # type: ignore[no-untyped-def]
    return evidence_status(reg, family=family, params=params or A)


def test_evidence_is_none_for_an_empty_registry_and_for_partial_passes(tmp_path: Path) -> None:
    reg = ExperimentRegistry(tmp_path)
    assert _gate(reg) is EvidenceStatus.NONE
    _rec(reg, "backtest", "development", True, A)
    _rec(reg, "backtest", "validation", True, A)
    assert _gate(reg) is EvidenceStatus.NONE  # test period never run


def test_evidence_needs_all_three_periods_for_the_requested_configuration(tmp_path: Path) -> None:
    reg = ExperimentRegistry(tmp_path)
    for period in ("development", "validation", "test"):
        _rec(reg, "backtest", period, True, A)
    assert _gate(reg) is EvidenceStatus.VALIDATED
    assert _gate(reg, params={"strategy": "b"}) is EvidenceStatus.NONE  # other strategy
    assert _gate(reg, family="model") is EvidenceStatus.NONE  # other family


def test_passes_spread_over_different_configurations_do_not_add_up(tmp_path: Path) -> None:
    reg = ExperimentRegistry(tmp_path)
    _rec(reg, "backtest", "development", True, A)
    _rec(reg, "backtest", "validation", True, {"strategy": "b"})
    _rec(reg, "backtest", "test", True, {"strategy": "c"})
    for params in (A, {"strategy": "b"}, {"strategy": "c"}):
        assert _gate(reg, params=params) is EvidenceStatus.NONE


def test_a_later_failure_revokes_the_evidence(tmp_path: Path) -> None:
    reg = ExperimentRegistry(tmp_path)
    for period in ("development", "validation", "test"):
        _rec(reg, "model", period, True, {"model": "m"})
    assert _gate(reg, "model", {"model": "m"}) is EvidenceStatus.VALIDATED
    _rec(reg, "model", "validation", False, {"model": "m"})
    assert _gate(reg, "model", {"model": "m"}) is EvidenceStatus.NONE


def test_periods_run_on_different_datasets_do_not_count(tmp_path: Path) -> None:
    reg = ExperimentRegistry(tmp_path)
    _rec(reg, "backtest", "development", True, A, datasets={"M15": "old"})
    _rec(reg, "backtest", "validation", True, A)
    _rec(reg, "backtest", "test", True, A)
    assert _gate(reg) is EvidenceStatus.NONE


def test_runs_from_a_dirty_working_tree_do_not_count(tmp_path: Path) -> None:
    reg = ExperimentRegistry(tmp_path)
    for period in ("development", "validation", "test"):
        _rec(reg, "backtest", period, True, A, dirty=period == "test")
    assert _gate(reg) is EvidenceStatus.NONE


def test_parameter_dict_order_does_not_matter(tmp_path: Path) -> None:
    reg = ExperimentRegistry(tmp_path)
    nested = {"strategy": "a", "cfg": {"x": 1, "y": 2}}
    for period in ("development", "validation", "test"):
        _rec(reg, "backtest", period, True, nested)
    assert _gate(reg, params={"cfg": {"y": 2, "x": 1}, "strategy": "a"}) is EvidenceStatus.VALIDATED
