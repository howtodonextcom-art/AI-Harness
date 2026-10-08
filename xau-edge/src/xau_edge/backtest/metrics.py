"""Backtest performance metrics (brief section 25).

Ratios that are mathematically undefined (no losses, no variance, no drawdown, no trades) are
``None``, never a made-up number or infinity, so they can be stored and compared safely.
Risk-adjusted ratios use daily equity closes on the FTMO day (midnight Prague) with 252 periods
per year.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
import polars as pl

_REQUIRED = ("entry_time", "exit_time", "net_pnl", "net_r", "gross_pnl")
_PERIODS_PER_YEAR = 252.0


@dataclass(frozen=True)
class Metrics:
    """Summary statistics of one backtest."""

    trade_count: int
    net_profit: float
    net_return: float
    profit_factor: float | None
    win_rate: float | None
    avg_win: float | None
    avg_loss: float | None
    avg_r: float | None
    expectancy: float | None
    longest_losing_streak: int
    max_drawdown: float
    max_drawdown_pct: float
    sharpe: float | None
    sortino: float | None
    calmar: float | None
    exposure: float


def _longest_streak(pnl: np.ndarray) -> int:
    best = run = 0
    for value in pnl:
        run = run + 1 if value < 0 else 0
        best = max(best, run)
    return best


def _daily_closes(equity: pl.DataFrame) -> np.ndarray:
    daily = (
        equity.with_columns(
            pl.col("timestamp").dt.convert_time_zone("Europe/Prague").dt.date().alias("_day")
        )
        .group_by("_day", maintain_order=True)
        .agg(pl.col("equity").last())
    )
    return daily["equity"].to_numpy()


def compute_metrics(trades: pl.DataFrame, equity: pl.DataFrame, initial_capital: float) -> Metrics:
    """Compute metrics from a trade list and the bar-level equity curve."""
    missing = [c for c in _REQUIRED if c not in trades.columns]
    if missing or "equity" not in equity.columns or "timestamp" not in equity.columns:
        msg = f"missing column(s): {', '.join(missing) or 'equity/timestamp'}"
        raise ValueError(msg)
    if equity.height == 0:
        msg = "equity curve is empty"
        raise ValueError(msg)

    pnl = trades["net_pnl"].to_numpy()
    r = trades["net_r"].to_numpy()
    n = int(pnl.size)
    wins, losses = pnl[pnl > 0], pnl[pnl < 0]

    values = equity["equity"].to_numpy()
    peak = np.maximum.accumulate(values)
    drawdown = peak - values
    dd_pct = drawdown / peak
    max_dd, max_dd_pct = float(drawdown.max()), float(dd_pct.max())
    net_return = float(values[-1] / initial_capital - 1.0)

    closes = _daily_closes(equity)
    rets = closes[1:] / closes[:-1] - 1.0 if closes.size > 1 else np.array([])
    sharpe = sortino = None
    if rets.size > 1:
        sd = float(rets.std(ddof=1))
        if sd > 0:
            sharpe = float(rets.mean() / sd * math.sqrt(_PERIODS_PER_YEAR))
        downside = float(np.sqrt(np.mean(np.minimum(rets, 0.0) ** 2)))
        if downside > 0:
            sortino = float(rets.mean() / downside * math.sqrt(_PERIODS_PER_YEAR))

    span_days = (equity["timestamp"][-1] - equity["timestamp"][0]).total_seconds() / 86_400
    calmar = None
    if max_dd_pct > 0 and span_days > 0:
        calmar = float(net_return * 365.0 / span_days / max_dd_pct)

    in_position = 0
    if n:
        ts = equity["timestamp"]
        inside = np.zeros(equity.height, dtype=bool)
        for entry, exit_ in zip(
            trades["entry_time"].to_list(), trades["exit_time"].to_list(), strict=True
        ):
            inside |= ((ts >= entry) & (ts <= exit_)).to_numpy()
        in_position = int(inside.sum())

    return Metrics(
        trade_count=n,
        net_profit=float(pnl.sum()),
        net_return=net_return,
        profit_factor=float(wins.sum() / -losses.sum()) if losses.size and wins.size else None,
        win_rate=float(wins.size / n) if n else None,
        avg_win=float(wins.mean()) if wins.size else None,
        avg_loss=float(losses.mean()) if losses.size else None,
        avg_r=float(r.mean()) if n else None,
        expectancy=float(pnl.mean()) if n else None,
        longest_losing_streak=_longest_streak(pnl),
        max_drawdown=max_dd,
        max_drawdown_pct=max_dd_pct,
        sharpe=sharpe,
        sortino=sortino,
        calmar=calmar,
        exposure=in_position / equity.height,
    )


def return_by_group(trades: pl.DataFrame, column: str) -> pl.DataFrame:
    """Net P&L, trade count, mean R and share of total net profit per value of ``column``."""
    if column not in trades.columns:
        msg = f"missing column: {column}"
        raise ValueError(msg)
    total = float(trades["net_pnl"].sum())
    return (
        trades.group_by(column)
        .agg(
            pl.col("net_pnl").sum().alias("net_pnl"),
            pl.len().alias("trades"),
            pl.col("net_r").mean().alias("mean_r"),
        )
        .with_columns(
            (pl.col("net_pnl") / total if total > 0 else pl.lit(None, dtype=pl.Float64)).alias(
                "share_of_profit"
            )
        )
        .sort(column)
    )
