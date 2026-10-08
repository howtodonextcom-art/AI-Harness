"""Strategy runner on synthetic frames (code paths only; no market meaning)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np
import polars as pl
import pytest

from tests.conftest import make_bars
from xau_edge.domain.timeframe import Timeframe
from xau_edge.evaluation.runner import (
    STRATEGIES,
    Frames,
    build_signals,
    execution_bars,
    run_strategy,
    strategy_params,
)
from xau_edge.risk.prop_rules import load_prop_profile

PROP = load_prop_profile(Path(__file__).parents[3] / "configs" / "prop" / "ftmo_2step.yaml")
START = datetime(2025, 3, 3, tzinfo=UTC)


def _walk(n: int, tf: Timeframe, seed: int) -> pl.DataFrame:
    rng = np.random.default_rng(seed)
    close = 2000 + np.cumsum(rng.normal(0, 1.0 * (tf.minutes / 5) ** 0.5, n))
    open_ = np.concatenate([[2000.0], close[:-1]])
    high = np.maximum(open_, close) + np.abs(rng.normal(0, 0.4, n))
    low = np.minimum(open_, close) - np.abs(rng.normal(0, 0.4, n))
    return make_bars(n, tf).with_columns(
        pl.Series("open", open_),
        pl.Series("high", high),
        pl.Series("low", low),
        pl.Series("close", close),
        pl.Series("tick_volume", rng.integers(50, 500, n)),
    )


def _frames() -> Frames:
    return Frames(
        m5=_walk(3000, Timeframe.M5, 1),
        m15=_walk(1000, Timeframe.M15, 2),
        h1=_walk(300, Timeframe.H1, 3),
    )


PERIOD = (START + timedelta(days=4), START + timedelta(days=10))


def test_unknown_strategy_is_rejected_with_the_valid_names() -> None:
    with pytest.raises(ValueError, match="baseline_a"):
        strategy_params("magic")


def test_strategy_params_identify_each_baseline() -> None:
    names = {strategy_params(s)["strategy"] for s in STRATEGIES}
    assert names == set(STRATEGIES)
    assert strategy_params("baseline_c")["window"] == 30


def test_execution_bars_are_inside_the_period_with_float_spread() -> None:
    bars = execution_bars(_frames(), PERIOD)
    assert (bars["timestamp"] >= PERIOD[0]).all()
    assert (bars["timestamp"] < PERIOD[1]).all()
    assert bars.schema["spread"] == pl.Float64
    assert bars.columns == ["timestamp", "open", "high", "low", "close", "spread"]


@pytest.mark.parametrize("strategy", ["baseline_a", "baseline_b"])
def test_signals_are_limited_to_the_period(strategy: str) -> None:
    sig, _ = build_signals(strategy, _frames(), PERIOD)
    assert sig.height > 0
    assert (sig["decision_time"] >= PERIOD[0]).all()
    assert (sig["decision_time"] < PERIOD[1]).all()
    assert "regime" in sig.columns


def test_run_strategy_returns_trades_metrics_and_a_verdict() -> None:
    run = run_strategy("baseline_b", _frames(), PERIOD, PROP, variants=3, n_resamples=100)
    assert run.strategy == "baseline_b"
    assert run.metrics.trade_count == run.trades.height
    assert "session" in run.trades.columns
    assert set(run.verdict.criteria) == {
        "min_trades",
        "ci_lower_above_zero",
        "profit_factor",
        "max_drawdown_r",
        "positive_folds",
        "robust_to_best_trades",
        "no_concentration",
    }
    assert run.verdict.variants == 3
    assert set(run.prop_feasibility) == {"daily", "max_loss"}


def test_the_prop_buffer_does_not_truncate_the_research_sample() -> None:
    # very large stop-outs would exhaust a 5% / 10% prop buffer quickly; research runs keep trading
    run = run_strategy("baseline_b", _frames(), PERIOD, PROP, variants=1, n_resamples=100)
    reasons = run.result.skipped["reason"].to_list() if run.result.skipped.height else []
    assert not any("MAX_LOSS_BUFFER" in r or "DAILY_LOSS_BUFFER" in r for r in reasons)
    assert run.result.kill_switch_reason == ""
