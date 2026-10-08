"""Baseline C and the analogue study: leakage-safe queries, thresholds, period handling."""

from __future__ import annotations

from datetime import UTC, datetime
from itertools import pairwise

import numpy as np
import polars as pl
import pytest

from tests.conftest import make_bars
from xau_edge.domain.timeframe import Timeframe
from xau_edge.strategies.baselines import SIGNAL_COLUMNS
from xau_edge.strategies.pattern import PatternConfig, analogue_study, baseline_c

CFG = PatternConfig(window=12, horizon_guard=24, k=8, outcome_horizon=6, min_matches=5, step=3)


def _bars(n: int = 700, seed: int = 4) -> pl.DataFrame:
    rng = np.random.default_rng(seed)
    close = 2000 + np.cumsum(rng.normal(0, 2, n)) + 15 * np.sin(np.arange(n) / 11)
    open_ = np.concatenate([[2000.0], close[:-1]]) + rng.normal(0, 0.6, n)
    high = np.maximum(open_, close) + np.abs(rng.normal(0, 1, n))
    low = np.minimum(open_, close) - np.abs(rng.normal(0, 1, n))
    return make_bars(n, Timeframe.M15).with_columns(
        pl.Series("open", open_),
        pl.Series("high", high),
        pl.Series("low", low),
        pl.Series("close", close),
        pl.Series("tick_volume", rng.integers(50, 500, n)),
    )


def test_study_has_one_row_per_step_inside_the_period() -> None:
    bars = _bars()
    start, end = bars["timestamp"][400], bars["timestamp"][600]
    study = analogue_study(bars, Timeframe.M15, CFG, period=(start, end))
    assert study.height > 0
    assert study["timestamp"].min() >= start
    assert study["timestamp"].max() < end
    idx = study["q_index"].to_list()
    assert all(b - a == CFG.step for a, b in pairwise(idx))
    assert {
        "timestamp",
        "decision_time",
        "q_index",
        "n_matches",
        "p_up",
        "p_down",
        "analogue_mean_atr",
        "realized_atr",
        "atr",
    } <= set(study.columns)


def test_probabilities_are_proper_and_matches_bounded_by_k() -> None:
    bars = _bars()
    study = analogue_study(
        bars, Timeframe.M15, CFG, period=(bars["timestamp"][300], bars["timestamp"][650])
    )
    assert (study["n_matches"] <= CFG.k).all()
    total = study["p_up"] + study["p_down"]
    assert (total <= 1.0 + 1e-12).all()
    assert ((study["p_up"] >= 0) & (study["p_down"] >= 0)).all()


def test_study_rows_do_not_depend_on_bars_after_the_query() -> None:
    bars = _bars()
    cut = 520
    period = (bars["timestamp"][350], bars["timestamp"][cut])
    full = analogue_study(bars, Timeframe.M15, CFG, period=period)
    shortened = analogue_study(bars.head(cut + 1), Timeframe.M15, CFG, period=period)
    cols = ["q_index", "n_matches", "p_up", "p_down", "analogue_mean_atr", "atr"]
    assert full.select(cols).equals(shortened.select(cols))


def test_analogue_statistics_ignore_garbage_written_after_the_query_horizon() -> None:
    bars = _bars()
    q = 500
    period = (bars["timestamp"][q], bars["timestamp"][q + 1])
    base = analogue_study(bars, Timeframe.M15, CFG, period=period)
    wrecked = bars.with_columns(
        pl.when(pl.int_range(pl.len()) > q).then(pl.col(c) * 7 + 3).otherwise(pl.col(c)).alias(c)
        for c in ("open", "high", "low", "close")
    )
    other = analogue_study(wrecked, Timeframe.M15, CFG, period=period)
    for col in ("p_up", "p_down", "analogue_mean_atr", "n_matches"):
        assert base[col].to_list() == other[col].to_list(), col
    # the one-bar period ends before the outcome horizon, so the realised value is clipped away
    assert base["realized_atr"].null_count() == 1


def test_queries_too_early_for_any_candidate_are_skipped() -> None:
    bars = _bars(200)
    study = analogue_study(
        bars, Timeframe.M15, CFG, period=(bars["timestamp"][0], bars["timestamp"][60])
    )
    assert study.height == 0 or (study["n_matches"] > 0).all()


def _study(**cols: list[float]) -> pl.DataFrame:
    n = len(next(iter(cols.values())))
    ts = [datetime(2026, 1, 1, tzinfo=UTC)] * n
    return pl.DataFrame(
        {"timestamp": ts, "decision_time": ts, "q_index": list(range(n)), "atr": [2.0] * n, **cols}
    )


def test_baseline_c_needs_enough_matches_and_a_sufficient_probability_edge() -> None:
    study = _study(
        n_matches=[20, 20, 20, 4, 20, 20, 15, 14, 20],
        p_up=[0.6, 0.5, 0.1, 0.9, 0.4, 0.55, 0.9, 0.9, 0.7],
        p_down=[0.2, 0.3, 0.4, 0.0, 0.2, 0.5, 0.0, 0.0, 0.5],
    )
    sig = baseline_c(study, PatternConfig(min_matches=15, edge_threshold=0.2))
    assert sig.columns == list(SIGNAL_COLUMNS)
    # row0 edge +0.4 long; row1 edge +0.2 inclusive long; row2 edge -0.3 short; row3 too few
    # matches; row4 edge +0.2 inclusive long; row5 edge +0.05 wait
    # row6 has exactly min_matches (inclusive), row7 one fewer, row8 edge 0.7-0.5 = 0.2 despite
    # floating-point error
    assert sig["direction"].to_list() == [1, 1, -1, 1, 1, 1]


def test_baseline_c_uses_the_configured_exit_distances() -> None:
    study = _study(n_matches=[20], p_up=[0.9], p_down=[0.0])
    sig = baseline_c(study, PatternConfig(stop_atr=1.0, target_atr=2.0, outcome_horizon=12))
    assert sig["stop_atr"][0] == 1.0
    assert sig["target_atr"][0] == 2.0
    assert sig["max_hold_bars"][0] == 12
    assert sig["strategy"][0] == "baseline_c"


def test_config_validation() -> None:
    with pytest.raises(ValueError, match="outcome_horizon"):
        PatternConfig(horizon_guard=10, outcome_horizon=20)
    with pytest.raises(ValueError, match="step"):
        PatternConfig(step=0)


def test_realised_outcomes_never_reach_into_the_next_period() -> None:
    bars = _bars()
    end_idx = 520
    period = (bars["timestamp"][480], bars["timestamp"][end_idx])
    study = analogue_study(bars, Timeframe.M15, CFG, period=period)
    late = study.filter(pl.col("q_index") + CFG.outcome_horizon >= end_idx)
    early = study.filter(pl.col("q_index") + CFG.outcome_horizon < end_idx)
    assert late.height > 0
    assert late["realized_atr"].null_count() == late.height
    assert early["realized_atr"].null_count() == 0


def test_baseline_c_attaches_regimes_by_timestamp() -> None:
    ts = [datetime(2026, 1, 1, tzinfo=UTC), datetime(2026, 1, 1, 0, 15, tzinfo=UTC)]
    study = pl.DataFrame(
        {
            "timestamp": pl.Series(ts, dtype=pl.Datetime("us", "UTC")),
            "decision_time": pl.Series(ts, dtype=pl.Datetime("us", "UTC")),
            "q_index": [0, 1],
            "atr": [2.0, 2.0],
            "n_matches": [20, 20],
            "p_up": [0.9, 0.9],
            "p_down": [0.0, 0.0],
        }
    )
    regimes = pl.DataFrame(
        {"timestamp": pl.Series(ts, dtype=pl.Datetime("us", "UTC")), "regime": ["RANGE", "SHOCK"]}
    )
    sig = baseline_c(study, PatternConfig(), regimes=regimes)
    assert sig["regime"].to_list() == ["RANGE", "SHOCK"]
