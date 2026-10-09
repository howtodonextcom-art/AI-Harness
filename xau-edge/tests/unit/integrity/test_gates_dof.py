from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pytest

from xau_edge.integrity.dof import (
    DesignEntry,
    DesignLedger,
    deflated_sharpe,
    expected_max_sharpe,
    probability_of_backtest_overfitting,
    reality_check_pvalue,
)
from xau_edge.integrity.gates import (
    OVER_STRICT,
    SUPPORTED,
    UNDER_STRICT,
    broker_gate,
    calibrate,
    classify,
    parameter_gate,
    temporal_gate,
)

# -- gate rules ----------------------------------------------------------------------------


def test_temporal_gate_needs_70_percent_positive_years_and_no_dominant_year() -> None:
    means = np.array([0.1] * 6 + [-0.1] * 2)
    profit = np.array([10.0] * 6 + [-5.0] * 2)
    assert temporal_gate(means, profit)
    assert not temporal_gate(np.array([0.1] * 5 + [-0.1] * 3), np.array([10.0] * 5 + [-5.0] * 3))
    spike = np.array([100.0, 5, 5, 5, 5, 5, 5, 5])
    assert not temporal_gate(np.full(8, 0.1), spike)
    assert not temporal_gate(np.array([]), np.array([]))


def test_parameter_gate_rejects_a_lucky_spike() -> None:
    assert parameter_gate(0.2, np.array([0.15, 0.12]))
    assert not parameter_gate(0.2, np.array([0.15, -0.01]))
    assert not parameter_gate(0.2, np.array([0.15, 0.05]))
    assert not parameter_gate(-0.1, np.array([0.1]))


def test_broker_gate() -> None:
    assert broker_gate(0.2, 0.12)
    assert not broker_gate(0.2, 0.05)
    assert not broker_gate(0.2, -0.1)


def test_classification_rule_is_fixed_and_total() -> None:
    assert classify(0.02, 0.8)[0] == SUPPORTED
    assert classify(0.30, 0.9)[0] == UNDER_STRICT
    assert classify(0.01, 0.2)[0] == OVER_STRICT
    assert classify(0.04, 0.55)[0] == "CONSERVATIVE"


def test_calibration_is_deterministic_and_every_gate_is_classified() -> None:
    first = calibrate(sims=120, seed=3)
    again = calibrate(sims=120, seed=3)
    assert first == again
    assert [g.gate for g in first] == ["temporal", "parameter", "broker"]
    for gate in first:
        assert gate.classification in {SUPPORTED, "CONSERVATIVE", OVER_STRICT, UNDER_STRICT}
        assert set(gate.pass_rate) == {"0.00R", "0.05R", "0.10R", "0.20R"}
        assert gate.pass_rate["0.20R"] >= gate.pass_rate["0.00R"]


# -- design ledger -------------------------------------------------------------------------


def entry(hid: str) -> DesignEntry:
    return DesignEntry(
        hypothesis_id=hid,
        recorded_at="2026-10-09T00:00:00+00:00",
        idea_origin="session transition literature",
        previous_experiments_known=["H01..H06 all rejected"],
        datasets_results_already_seen=["dev-H, val-H"],
        labels_considered=["triple barrier"],
        horizons_considered=["4h", "8h"],
        filters_considered=["session"],
        parameters_considered=["theta"],
        rejected_alternatives=["tick-level version (no data)"],
        ai_suggestions_consulted=["assistant proposed the grid"],
    )


def test_design_ledger_is_append_only_and_tamper_evident(tmp_path: Path) -> None:
    ledger = DesignLedger(tmp_path / "dof.jsonl")
    assert ledger.verify()
    ledger.append(entry("H07"))
    ledger.append(entry("H08"))
    assert ledger.verify()
    assert [e.hypothesis_id for e in ledger.entries()] == ["H07", "H08"]
    with pytest.raises(ValueError, match="already recorded"):
        ledger.append(entry("H07"))
    path = tmp_path / "dof.jsonl"
    path.write_text(
        path.read_text(encoding="utf-8").replace("literature", "rumour"), encoding="utf-8"
    )
    assert not ledger.verify()
    with pytest.raises(ValueError, match="does not verify"):
        ledger.append(entry("H09"))


# -- diagnostics ---------------------------------------------------------------------------


def test_more_trials_raise_the_luck_benchmark() -> None:
    assert expected_max_sharpe(1, 0.1) == 0.0
    assert expected_max_sharpe(100, 0.1) > expected_max_sharpe(10, 0.1) > 0
    with pytest.raises(ValueError, match="n_trials"):
        expected_max_sharpe(0, 0.1)


def test_deflated_sharpe_falls_as_trials_grow() -> None:
    few = deflated_sharpe(0.15, 500, skew=0.0, kurt=3.0, n_trials=2, var_trial_sharpe=0.01)
    many = deflated_sharpe(0.15, 500, skew=0.0, kurt=3.0, n_trials=200, var_trial_sharpe=0.01)
    assert many < few
    assert 0 <= many <= 1
    with pytest.raises(ValueError, match="3 observations"):
        deflated_sharpe(0.1, 2, skew=0, kurt=3, n_trials=5, var_trial_sharpe=0.01)


def test_pbo_is_high_for_pure_noise_trials_and_low_for_a_real_winner() -> None:
    rng = np.random.default_rng(0)
    noise = rng.standard_normal((400, 20))
    pbo = probability_of_backtest_overfitting(noise)
    assert 0.35 < pbo < 0.65  # pure noise: about one half
    real = rng.standard_normal((400, 20))
    real[:, 7] += 0.5
    assert probability_of_backtest_overfitting(real) < 0.1
    assert math.isnan(probability_of_backtest_overfitting(noise[:, :1]))


def test_reality_check_does_not_reward_the_best_of_noise() -> None:
    rng = np.random.default_rng(1)
    noise = rng.standard_normal((300, 15))
    assert reality_check_pvalue(noise, seed=2, draws=300) > 0.05
    signal = noise.copy()
    signal[:, 3] += 0.6
    assert reality_check_pvalue(signal, seed=2, draws=300) < 0.05
    assert reality_check_pvalue(signal, seed=2, draws=300) == reality_check_pvalue(
        signal, seed=2, draws=300
    )
