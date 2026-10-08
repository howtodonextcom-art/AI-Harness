"""Power test of the backtest + edge pipeline: a PLANTED edge must be detected, a null must not.

Without this, "every baseline failed" could simply mean the pipeline cannot see anything. The bars
are synthetic; the planted effect is a fixed upward drift after each signal time.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import numpy as np
import polars as pl

from xau_edge.backtest.engine import BacktestConfig, run_backtest
from xau_edge.backtest.metrics import compute_metrics
from xau_edge.domain.timeframe import Timeframe
from xau_edge.evaluation.edge import evaluate_edge
from xau_edge.risk.engine import RiskLimits
from xau_edge.risk.prop_rules import PropProfile

START = datetime(2026, 1, 5, tzinfo=UTC)  # a Monday
DAYS = 100
N = DAYS * 288
PERIOD = (START, START + timedelta(days=DAYS))
OPEN_PROP = PropProfile(
    name="open",
    source="x",
    verified_on="2026-01-01",
    daily_loss_limit_pct=99.0,
    max_loss_limit_pct=99.0,
    max_loss_kind="static",
    internal_buffer_pct_of_limit=0.0,
)


def _market(plant_edge: bool, seed: int = 1) -> tuple[pl.DataFrame, pl.DataFrame]:
    rng = np.random.default_rng(seed)
    step = rng.normal(0.0, 0.25, N)
    signal_bars = np.arange(40, N - 40, 144)  # a signal every 12 hours
    if plant_edge:
        for k, b in enumerate(signal_bars):
            if k % 5 != 0:  # one signal in five is left unplanted, so losses occur
                step[b + 1 : b + 7] += 0.9  # +5.4 over the next 30 minutes
    close = 2000.0 + np.cumsum(step)
    open_ = np.concatenate([[2000.0], close[:-1]])
    high = np.maximum(open_, close) + 0.1
    low = np.minimum(open_, close) - 0.1
    ts = [START + timedelta(minutes=5 * i) for i in range(N)]
    bars = pl.DataFrame(
        {
            "timestamp": pl.Series(ts, dtype=pl.Datetime("us", "UTC")),
            "open": open_,
            "high": high,
            "low": low,
            "close": close,
            "spread": np.full(N, 25.0),
        }
    )
    decision = [ts[b] + timedelta(minutes=5) for b in signal_bars]  # decided at the close of bar b
    sessions = np.array(["ASIA", "LONDON", "NEW_YORK", "LONDON_NY_OVERLAP"])
    regimes = np.array(["RANGE", "TREND_UP", "TREND_DOWN"])
    signals = pl.DataFrame(
        {
            "timestamp": pl.Series([ts[b] for b in signal_bars], dtype=pl.Datetime("us", "UTC")),
            "decision_time": pl.Series(decision, dtype=pl.Datetime("us", "UTC")),
            "direction": pl.Series(np.ones(len(decision), dtype=np.int8)),
            "atr": np.ones(len(decision)),
            "stop_atr": np.full(len(decision), 1.5),
            "target_atr": np.full(len(decision), 3.0),
            "max_hold_bars": pl.Series(np.full(len(decision), 12, dtype=np.int32)),
            "strategy": ["planted"] * len(decision),
            "regime": regimes[np.arange(len(decision)) % 3],
        }
    )
    del sessions
    return bars, signals


def _evaluate(plant_edge: bool):  # type: ignore[no-untyped-def]
    bars, signals = _market(plant_edge)
    cfg = BacktestConfig(
        signal_timeframe=Timeframe.M5,
        require_news_calendar=False,
        limits=RiskLimits(
            daily_risk_budget_pct=50.0, consecutive_loss_limit=1000, max_total_lots=1e6, max_lot=1e6
        ),
    )
    result = run_backtest(signals, bars, cfg, OPEN_PROP)
    trades = result.trades.with_columns(
        pl.Series(
            "session",
            np.array(["ASIA", "LONDON", "NEW_YORK", "LONDON_NY_OVERLAP"])[
                np.arange(result.trades.height) % 4
            ],
        )
    )
    return (
        trades,
        result,
        evaluate_edge(
            trades,
            result.equity,
            period=PERIOD,
            variants=1,
            initial_capital=100_000.0,
            n_resamples=500,
        ),
    )


def test_a_planted_edge_passes_every_criterion() -> None:
    trades, result, verdict = _evaluate(plant_edge=True)
    assert trades.height >= 150
    assert trades["net_r"].mean() > 0.8  # large planted edge, after spread and slippage
    failed = {k: c for k, c in verdict.criteria.items() if not c.passed}
    assert not failed, failed
    assert compute_metrics(trades, result.equity, 100_000.0).profit_factor > 5  # type: ignore[operator]


def test_the_same_market_without_the_edge_fails() -> None:
    trades, _, verdict = _evaluate(plant_edge=False)
    assert trades.height >= 150
    assert trades["net_r"].mean() < 0  # costs make a no-edge strategy a loser
    assert not verdict.passed
    assert not verdict.criteria["ci_lower_above_zero"].passed
