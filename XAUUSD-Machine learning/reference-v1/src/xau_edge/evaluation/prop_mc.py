"""Prop-firm feasibility Monte Carlo (T1.5 filter): how much risk per trade survives the limits.

Input is the per-trade net R of a run with each trade's exit time. Trades are grouped into
prop-firm trading days (midnight Europe/Prague, the FTMO day boundary) and whole days are
resampled with replacement (day-block bootstrap), so within-day clustering is kept.

For a per-trade risk ``r`` (percent of INITIAL capital, fixed, not compounded) a simulated path
of ``h`` trading days breaches when, on any day:

* the day's loss reaches the daily limit (5% of initial capital) measured against the day-start
  balance. Trade order inside a day is known (exit time), so the day's WORST running cumulative
  loss is used, not only its close (conservative); or
* equity reaches the static max-loss floor (initial capital minus 10%), again using the day's
  worst running point.

Floating losses inside an open trade beyond its realised R are not modelled; a stop that gaps
is already in the realised R. All functions are pure (no I/O) and deterministic for a seed.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime
from typing import Final
from zoneinfo import ZoneInfo

import numpy as np
from numpy.typing import ArrayLike, NDArray

Floats = NDArray[np.float64]

PRAGUE: Final = ZoneInfo("Europe/Prague")
DAILY_LOSS_PCT: Final = 5.0
MAX_LOSS_PCT: Final = 10.0
HORIZONS: Final = (30, 60, 90)
RISK_GRID_PCT: Final = tuple(round(0.05 * k, 2) for k in range(1, 21))
"""0.05% .. 1.00% in steps of 0.05%."""
MAX_BREACH_PROBABILITY: Final = 0.05
OVERRIDE_CAP_PCT: Final = 0.25
N_PATHS: Final = 10_000
SEED: Final = 7
_EPS: Final = 1e-9


@dataclass(frozen=True)
class DailyBlocks:
    """One entry per prop day: the day's total R and its worst running cumulative R (<= 0)."""

    days: tuple[date, ...]
    total_r: Floats
    worst_r: Floats


@dataclass(frozen=True)
class PropMcResult:
    """Breach probabilities per risk level and horizon, and the resulting risk recommendation."""

    breach_probability: dict[float, dict[int, float]]
    """``{risk_pct: {horizon_days: P(breach within horizon)}}``."""
    max_safe_risk_pct: float | None
    """Largest grid risk with P(breach within the longest horizon) <= 5%; None if none."""
    override_risk_pct: float | None
    """``min(max_safe_risk_pct, 0.25)``; None when every risk level is refused."""
    n_days: int
    n_paths: int
    seed: int


def daily_blocks(
    net_r: ArrayLike,
    exit_times: Sequence[datetime],
    *,
    all_days: Sequence[date] | None = None,
) -> DailyBlocks:
    """Group trades into Prague days (ordered by exit time) with day total and worst running R.

    ``all_days`` optionally lists every trading day of the sample (Prague dates); days without a
    trade then enter the bootstrap as flat days. Without it only days with trades are used, which
    is conservative (every simulated day carries trades).
    """
    r = np.asarray(net_r, dtype=np.float64)
    if r.ndim != 1 or r.size != len(exit_times):
        msg = f"net_r and exit_times must be 1-D with the same length, got {r.shape}"
        raise ValueError(msg)
    if r.size == 0:
        msg = "cannot simulate without trades"
        raise ValueError(msg)
    if not np.isfinite(r).all():
        msg = "net_r must be finite"
        raise ValueError(msg)
    if any(t.tzinfo is None for t in exit_times):
        msg = "exit times must be timezone-aware"
        raise ValueError(msg)
    order = sorted(range(r.size), key=lambda i: exit_times[i])
    per_day: dict[date, list[float]] = {}
    for i in order:
        per_day.setdefault(exit_times[i].astimezone(PRAGUE).date(), []).append(float(r[i]))
    if all_days is not None:
        for d in all_days:
            per_day.setdefault(d, [])
    days = tuple(sorted(per_day))
    total = np.array([sum(per_day[d]) for d in days], dtype=np.float64)
    worst = np.array(
        [min(0.0, float(np.cumsum(per_day[d]).min())) if per_day[d] else 0.0 for d in days],
        dtype=np.float64,
    )
    return DailyBlocks(days, total, worst)


def breach_probabilities(
    blocks: DailyBlocks,
    risk_pct: float,
    *,
    horizons: Sequence[int] = HORIZONS,
    n_paths: int = N_PATHS,
    seed: int = SEED,
    daily_loss_pct: float = DAILY_LOSS_PCT,
    max_loss_pct: float = MAX_LOSS_PCT,
) -> dict[int, float]:
    """P(breach within each horizon) for one per-trade risk (percent of initial capital)."""
    return _simulate(
        blocks,
        (risk_pct,),
        horizons=horizons,
        n_paths=n_paths,
        seed=seed,
        daily_loss_pct=daily_loss_pct,
        max_loss_pct=max_loss_pct,
    )[risk_pct]


def _simulate(
    blocks: DailyBlocks,
    risks: Sequence[float],
    *,
    horizons: Sequence[int],
    n_paths: int,
    seed: int,
    daily_loss_pct: float,
    max_loss_pct: float,
) -> dict[float, dict[int, float]]:
    if not horizons or min(horizons) < 1:
        msg = "horizons must be positive day counts"
        raise ValueError(msg)
    if n_paths < 1:
        msg = "n_paths must be >= 1"
        raise ValueError(msg)
    if any(r <= 0 for r in risks):
        msg = "risk levels must be > 0"
        raise ValueError(msg)
    length = max(horizons)
    rng = np.random.default_rng(seed)
    picks = rng.integers(0, blocks.total_r.size, size=(n_paths, length))
    total = blocks.total_r[picks]
    worst = blocks.worst_r[picks]
    closed_before = np.cumsum(total, axis=1) - total  # cumulative R at each day's start
    out: dict[float, dict[int, float]] = {}
    for risk in risks:
        day_loss = -risk * worst  # percent of initial capital, vs the day-start balance
        low = risk * (closed_before + worst)  # worst equity change vs initial capital
        breach = (day_loss >= daily_loss_pct - _EPS) | (low <= -max_loss_pct + _EPS)
        first = np.where(breach.any(axis=1), breach.argmax(axis=1), length)
        out[risk] = {h: float(np.mean(first < h)) for h in horizons}
    return out


def prop_monte_carlo(
    net_r: ArrayLike,
    exit_times: Sequence[datetime],
    *,
    all_days: Sequence[date] | None = None,
    risk_grid_pct: Sequence[float] = RISK_GRID_PCT,
    horizons: Sequence[int] = HORIZONS,
    max_breach_probability: float = MAX_BREACH_PROBABILITY,
    n_paths: int = N_PATHS,
    seed: int = SEED,
    daily_loss_pct: float = DAILY_LOSS_PCT,
    max_loss_pct: float = MAX_LOSS_PCT,
) -> PropMcResult:
    """Breach probabilities on the risk grid and the largest risk with P(breach, 90d) <= 5%.

    Every risk level is simulated on the SAME resampled paths (common random numbers), so the
    probabilities are comparable across the grid.
    """
    blocks = daily_blocks(net_r, exit_times, all_days=all_days)
    grid = tuple(float(r) for r in risk_grid_pct)
    probs = _simulate(
        blocks,
        grid,
        horizons=horizons,
        n_paths=n_paths,
        seed=seed,
        daily_loss_pct=daily_loss_pct,
        max_loss_pct=max_loss_pct,
    )
    longest = max(horizons)
    safe = [r for r in grid if probs[r][longest] <= max_breach_probability]
    best = max(safe) if safe else None
    return PropMcResult(
        breach_probability=probs,
        max_safe_risk_pct=best,
        override_risk_pct=None if best is None else min(best, OVERRIDE_CAP_PCT),
        n_days=len(blocks.days),
        n_paths=n_paths,
        seed=seed,
    )
