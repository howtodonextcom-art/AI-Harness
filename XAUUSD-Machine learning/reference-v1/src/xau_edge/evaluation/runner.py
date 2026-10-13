"""Run one baseline strategy over one evaluation period and judge it against the edge criteria."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

import polars as pl

from xau_edge.backtest.engine import BacktestConfig, BacktestResult, prop_breaches, run_backtest
from xau_edge.backtest.metrics import Metrics, compute_metrics
from xau_edge.domain.timeframe import Timeframe
from xau_edge.evaluation.edge import EdgeVerdict, evaluate_edge
from xau_edge.features.sessions import session_features
from xau_edge.risk.engine import RiskLimits
from xau_edge.risk.prop_rules import PropProfile
from xau_edge.strategies.baselines import (
    BaselineAConfig,
    BaselineBConfig,
    baseline_a,
    baseline_b,
)
from xau_edge.strategies.context import build_context
from xau_edge.strategies.pattern import PatternConfig, analogue_study, baseline_c

STRATEGIES = ("baseline_a", "baseline_b", "baseline_c")
_EXEC_COLUMNS = ("timestamp", "open", "high", "low", "close", "spread")


@dataclass(frozen=True)
class Frames:
    """Validated bar frames of the three timeframes used by the baselines."""

    m5: pl.DataFrame
    m15: pl.DataFrame
    h1: pl.DataFrame


@dataclass(frozen=True)
class StrategyRun:
    """Everything produced by one strategy-period run."""

    strategy: str
    period: tuple[datetime, datetime]
    result: BacktestResult
    trades: pl.DataFrame
    metrics: Metrics
    verdict: EdgeVerdict
    signal_count: int
    params: dict[str, Any]
    prop_feasibility: dict[str, Any]


def strategy_params(strategy: str) -> dict[str, Any]:
    """The fixed, pre-registered parameters of a strategy (used as its registry identity)."""
    configs: dict[str, Any] = {
        "baseline_a": BaselineAConfig(),
        "baseline_b": BaselineBConfig(),
        "baseline_c": PatternConfig(),
    }
    if strategy not in configs:
        msg = f"unknown strategy {strategy!r}; choose from {list(STRATEGIES)}"
        raise ValueError(msg)
    return {"strategy": strategy, **configs[strategy].model_dump(mode="json")}


def build_signals(
    strategy: str, frames: Frames, period: tuple[datetime, datetime]
) -> tuple[pl.DataFrame, Timeframe]:
    """Signals decided inside ``period`` and the timeframe they are expressed in."""
    start, end = period
    if strategy == "baseline_a":
        sig = baseline_a(
            build_context(frames.m5, Timeframe.M5),
            build_context(frames.m15, Timeframe.M15),
            build_context(frames.h1, Timeframe.H1),
        )
        tf = Timeframe.M5
    elif strategy == "baseline_b":
        sig = baseline_b(build_context(frames.m15, Timeframe.M15))
        tf = Timeframe.M15
    elif strategy == "baseline_c":
        study = analogue_study(frames.m15, Timeframe.M15, PatternConfig(), period=period)
        ctx = build_context(frames.m15, Timeframe.M15)
        sig = baseline_c(study, PatternConfig(), regimes=ctx.select("timestamp", "regime"))
        tf = Timeframe.M15
    else:
        strategy_params(strategy)  # raises with the list of valid names
        raise AssertionError  # pragma: no cover
    return sig.filter((pl.col("decision_time") >= start) & (pl.col("decision_time") < end)), tf


def execution_bars(frames: Frames, period: tuple[datetime, datetime]) -> pl.DataFrame:
    """M5 bars inside the period with a float spread column."""
    start, end = period
    return (
        frames.m5.filter((pl.col("timestamp") >= start) & (pl.col("timestamp") < end))
        .select(
            "timestamp",
            "open",
            "high",
            "low",
            "close",
            pl.col("spread").cast(pl.Float64).alias("spread"),
        )
        .sort("timestamp")
    )


def run_strategy(
    strategy: str,
    frames: Frames,
    period: tuple[datetime, datetime],
    prop: PropProfile,
    *,
    variants: int,
    initial_capital: float = 100_000.0,
    seed: int = 7,
    n_resamples: int = 2000,
) -> StrategyRun:
    """Backtest ``strategy`` on ``period`` (research run, no news calendar) and judge the edge."""
    signals, tf = build_signals(strategy, frames, period)
    return judge_signals(
        strategy,
        signals,
        tf,
        frames,
        period,
        prop,
        params=strategy_params(strategy),
        variants=variants,
        initial_capital=initial_capital,
        seed=seed,
        n_resamples=n_resamples,
    )


def judge_signals(  # noqa: PLR0917 - a run is defined by these independent inputs
    name: str,
    signals: pl.DataFrame,
    signal_timeframe: Timeframe,
    frames: Frames,
    period: tuple[datetime, datetime],
    prop: PropProfile,
    *,
    params: dict[str, Any],
    variants: int,
    initial_capital: float = 100_000.0,
    seed: int = 7,
    n_resamples: int = 2000,
) -> StrategyRun:
    """Backtest any signal set on ``period`` and judge it against the seven edge criteria."""
    bars = execution_bars(frames, period)
    config = BacktestConfig(
        signal_timeframe=signal_timeframe,
        initial_capital=initial_capital,
        require_news_calendar=False,
        # research runs must not be thinned by path-dependent per-day throttles either
        limits=RiskLimits(daily_risk_budget_pct=100.0, consecutive_loss_limit=10_000),
    )
    # Strategy research must not be truncated by the prop-firm buffer (a 5% drawdown would stop
    # every later trade and hide the rest of the sample), so the engine runs with the prop limits
    # opened up; feasibility under the REAL profile is measured separately from the equity curve.
    open_prop = prop.model_copy(
        update={
            "daily_loss_limit_pct": 99.0,
            "max_loss_limit_pct": 99.0,
            "max_loss_kind": "static",
            "internal_buffer_pct_of_limit": 0.0,
        }
    )
    result = run_backtest(signals, bars, config, open_prop)
    trades = result.trades
    if trades.height:
        sessions = session_features(trades["entry_time"])["trading_session"]
        trades = trades.with_columns(sessions.alias("session"))
    else:
        trades = trades.with_columns(pl.lit(None, dtype=pl.String).alias("session"))
    metrics = compute_metrics(trades, result.equity, initial_capital)
    verdict = evaluate_edge(
        trades,
        result.equity,
        period=period,
        variants=variants,
        initial_capital=initial_capital,
        seed=seed,
        n_resamples=n_resamples,
    )
    return StrategyRun(
        name,
        period,
        result,
        trades,
        metrics,
        verdict,
        signals.height,
        params,
        prop_breaches(result.equity, prop, initial_capital=initial_capital),
    )
