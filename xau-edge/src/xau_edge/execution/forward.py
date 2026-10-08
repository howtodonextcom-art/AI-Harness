"""Replay and forward-test tooling around the paper trader (Epic 18).

``replay`` walks historical bars as if they arrived live: M5 bars update the paper broker in time
order and a signal is requested at every M15 close, using only information available then. It
exercises the whole paper pipeline, but it is NOT forward evidence: the data already existed. A
real forward test needs the same loop fed by new bars as they close, for weeks; this module
labels its mode and ``compare_paper_to_backtest`` refuses to draw conclusions from a small sample.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import polars as pl

from xau_edge.domain.timeframe import Timeframe
from xau_edge.evaluation.bootstrap import block_bootstrap_ci
from xau_edge.execution.interface import ClosedTrade
from xau_edge.execution.paper import MarketBar
from xau_edge.execution.trader import PaperTrader
from xau_edge.signals.engine import MarketFrames
from xau_edge.signals.schema import Signal

MIN_TRADES_FOR_CONCLUSION = 100


@dataclass
class ReplayResult:
    """What a replay produced."""

    mode: str = "replay"
    decisions: int = 0
    accepted: int = 0
    refusals: dict[str, int] = field(default_factory=dict)
    trades: list[ClosedTrade] = field(default_factory=list)


def replay(
    frames: MarketFrames,
    trader: PaperTrader,
    signal_at: Callable[[datetime], Signal],
    start: datetime,
    end: datetime,
) -> ReplayResult:
    """Feed M5 bars to the paper broker and decide at each M15 close in ``[start, end]``."""
    m5 = frames.m5.filter(
        (pl.col("timestamp") + Timeframe.M5.delta >= start)
        & (pl.col("timestamp") + Timeframe.M5.delta <= end)
    ).sort("timestamp")
    result = ReplayResult(mode=trader.broker.mode)
    for row in m5.iter_rows(named=True):
        close_time: datetime = row["timestamp"] + Timeframe.M5.delta
        bar = MarketBar(
            time=close_time,
            open=row["open"],
            high=row["high"],
            low=row["low"],
            close=row["close"],
            spread_points=float(row["spread"]),
        )
        result.trades.extend(trader.on_bar(bar))
        if close_time.minute % Timeframe.M15.minutes == 0:
            signal = signal_at(close_time)
            result.decisions += 1
            outcome = trader.on_signal(signal, close_time, spread_points=bar.spread_points)
            if outcome.accepted:
                result.accepted += 1
            else:
                for reason in outcome.reasons:
                    result.refusals[reason] = result.refusals.get(reason, 0) + 1
    return result


def compare_paper_to_backtest(
    paper: list[ClosedTrade], backtest_trades: pl.DataFrame, *, mode: str = "forward"
) -> dict[str, Any]:
    """Compare mean R of paper trades with a backtest; no conclusion below the sample guard.

    ``mode='replay'`` trades (historical bars) can never form a conclusion. R here divides by the
    risk implied by the actual fill (entry price to stop), slightly larger than the backtest's
    signal-based risk, so paper R is marginally smaller for the same trade.
    """
    paper_r = [t.net_pnl / t.risk_amount for t in paper if t.risk_amount > 0]
    bt_r = backtest_trades["net_r"].to_numpy()
    report: dict[str, Any] = {
        "paper_trades": len(paper_r),
        "backtest_trades": int(bt_r.size),
        "paper_mean_r": float(sum(paper_r) / len(paper_r)) if paper_r else None,
        "backtest_mean_r": float(bt_r.mean()) if bt_r.size else None,
        "mode": mode,
        "sufficient_sample": mode == "forward" and len(paper_r) >= MIN_TRADES_FOR_CONCLUSION,
        "backtest_within_paper_interval": None,
    }
    if mode != "forward":
        report["conclusion"] = "REPLAY: historical bars are not forward evidence; no conclusion"
        return report
    if not report["sufficient_sample"]:
        report["conclusion"] = (
            f"INSUFFICIENT SAMPLE: {len(paper_r)} paper trades (need {MIN_TRADES_FOR_CONCLUSION}); "
            "no claim about live behaviour can be made"
        )
        return report
    days = [t.exit_time.date().isoformat() for t in paper if t.risk_amount > 0]
    lo, hi = block_bootstrap_ci(paper_r, days)
    inside = report["backtest_mean_r"] is not None and lo <= report["backtest_mean_r"] <= hi
    report["paper_interval"] = [lo, hi]
    report["backtest_within_paper_interval"] = bool(inside)
    report["conclusion"] = (
        "paper results are consistent with the backtest (not distinguishable at this sample size)"
        if inside
        else "paper results diverge from the backtest: investigate before trusting either"
    )
    return report
