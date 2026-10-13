"""The seven edge criteria of docs/evals/edge-criteria.md as executable checks.

Every criterion must hold; there is no partial credit. The inputs are the backtest's trade list
(net of costs) and equity curve for ONE evaluation period.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime
from itertools import pairwise
from typing import Any

import numpy as np
import polars as pl

from xau_edge.backtest.metrics import compute_metrics, return_by_group
from xau_edge.evaluation.bootstrap import block_bootstrap_ci

MIN_TRADES = 100
MIN_PROFIT_FACTOR = 1.2
MAX_DRAWDOWN_R = 15.0
FOLDS = 4
MIN_POSITIVE_FOLDS = 3
TRIM_FRACTION = 0.05
MAX_SHARE = 0.60
BASE_ALPHA = 0.05
_REQUIRED = ("entry_time", "exit_time", "net_pnl", "net_r", "gross_pnl", "session", "regime")


@dataclass(frozen=True)
class CriterionResult:
    """One criterion: whether it passed, the measured value and the threshold."""

    passed: bool
    value: float | int | None
    threshold: float | int


@dataclass(frozen=True)
class EdgeVerdict:
    """All criteria and the overall result."""

    criteria: dict[str, CriterionResult]
    variants: int
    alpha: float

    @property
    def passed(self) -> bool:
        """True only if every criterion passed."""
        return all(c.passed for c in self.criteria.values())

    def as_dict(self) -> dict[str, Any]:
        """JSON-safe form for the experiment registry."""
        out: dict[str, Any] = {
            name: {"passed": c.passed, "value": c.value, "threshold": c.threshold}
            for name, c in self.criteria.items()
        }
        out["passed"] = self.passed
        out["variants"] = self.variants
        out["alpha"] = self.alpha
        return out


def fold_bounds(period: tuple[datetime, datetime], count: int) -> list[tuple[datetime, datetime]]:
    """Split ``period`` into ``count`` contiguous parts of equal duration."""
    start, end = period
    width = (end - start) / count
    edges = [start + width * i for i in range(count)] + [end]
    return list(pairwise(edges))


def _max_drawdown_r(net_r: np.ndarray) -> float:
    curve = np.concatenate([[0.0], np.cumsum(net_r)])
    return float((np.maximum.accumulate(curve) - curve).max())


def _finite(value: float | None) -> float | None:
    return None if value is None or not math.isfinite(value) else float(value)


def evaluate_edge(
    trades: pl.DataFrame,
    equity: pl.DataFrame,
    *,
    period: tuple[datetime, datetime],
    variants: int,
    initial_capital: float,
    seed: int = 7,
    n_resamples: int = 2000,
) -> EdgeVerdict:
    """Apply the seven criteria to one period's trades."""
    missing = [c for c in _REQUIRED if c not in trades.columns]
    if missing:
        msg = f"missing column(s): {', '.join(missing)}"
        raise ValueError(msg)
    if variants < 1:
        msg = f"variants must be >= 1, got {variants}"
        raise ValueError(msg)
    alpha = BASE_ALPHA / variants
    n = trades.height
    net_r = trades.sort("entry_time")["net_r"].to_numpy()
    metrics = compute_metrics(trades, equity, initial_capital)
    results: dict[str, CriterionResult] = {}

    results["min_trades"] = CriterionResult(n >= MIN_TRADES, n, MIN_TRADES)

    if n >= 2:
        days = trades.sort("entry_time")["entry_time"].dt.date().to_numpy()
        lower = block_bootstrap_ci(net_r, days, alpha=alpha, n_resamples=n_resamples, seed=seed)[0]
    else:
        lower = float("nan")
    results["ci_lower_above_zero"] = CriterionResult(lower > 0, _finite(lower), 0.0)

    pf = metrics.profit_factor
    pnl = trades["net_pnl"].to_numpy() if n else np.array([])
    no_losses = bool(n) and bool((pnl > 0).any()) and not bool((pnl < 0).any())
    results["profit_factor"] = CriterionResult(
        no_losses or (pf is not None and pf >= MIN_PROFIT_FACTOR), _finite(pf), MIN_PROFIT_FACTOR
    )

    dd_r = _max_drawdown_r(net_r) if n else 0.0
    results["max_drawdown_r"] = CriterionResult(
        n > 0 and dd_r <= MAX_DRAWDOWN_R, dd_r, MAX_DRAWDOWN_R
    )

    positive = 0
    for a, b in fold_bounds(period, FOLDS):
        fold = trades.filter((pl.col("entry_time") >= a) & (pl.col("entry_time") < b))
        if fold.height and float(fold["net_r"].mean()) > 0:  # type: ignore[arg-type]
            positive += 1
    results["positive_folds"] = CriterionResult(
        positive >= MIN_POSITIVE_FOLDS, positive, MIN_POSITIVE_FOLDS
    )

    if n:
        drop = math.ceil(TRIM_FRACTION * n)
        trimmed_mean = float(np.sort(net_r)[: n - drop].mean()) if n - drop > 0 else float("nan")
    else:
        trimmed_mean = float("nan")
    results["robust_to_best_trades"] = CriterionResult(trimmed_mean > 0, _finite(trimmed_mean), 0.0)

    total_profit = float(trades["net_pnl"].sum()) if n else 0.0
    worst_share: float | None = None
    if total_profit > 0:
        shares = []
        for column in ("session", "regime"):
            grouped = return_by_group(
                trades.with_columns(pl.col(column).fill_null("UNKNOWN")), column
            )
            shares.append(float(grouped["share_of_profit"].max()))  # type: ignore[arg-type]
        worst_share = max(shares)
    results["no_concentration"] = CriterionResult(
        worst_share is not None and worst_share <= MAX_SHARE, _finite(worst_share), MAX_SHARE
    )
    return EdgeVerdict(results, variants, alpha)
