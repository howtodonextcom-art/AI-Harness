"""Historical outcome engine: what happened after a given bar (brief section 16).

All quantities are measured from the close of the anchor bar ``e`` (the reference price, known when
the bar closes) over the following ``h`` bars ``e+1 .. e+h`` and are expressed in units of the
anchor's ATR, so outcomes from different volatility regimes are comparable. Costs are NOT included
here; they belong to the backtest.

For a hypothetical LONG with stop ``stop_atr`` and target ``target_atr`` (ATR multiples; mirrored
for SHORT) the first barrier touched within the horizon decides the result. When a single bar
reaches both barriers the stop is assumed to come first (conservative). An unresolved trade is
marked to market at the horizon close. ``long_r`` / ``short_r`` are in R, where 1R is the stop
distance.
"""

from __future__ import annotations

from itertools import pairwise
from typing import NamedTuple

import numpy as np
from numpy.lib.stride_tricks import sliding_window_view
from numpy.typing import ArrayLike, NDArray
from pydantic import BaseModel, ConfigDict, Field, field_validator

Floats = NDArray[np.float64]
Ints = NDArray[np.int8]


class OutcomeConfig(BaseModel):
    """Horizons, the neutral band and the barrier distances."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    horizons: tuple[int, ...] = (5, 10, 20, 30, 60)
    neutral_threshold_atr: float = Field(default=0.5, ge=0)
    stop_atr: float = Field(default=1.5, gt=0)
    target_atr: float = Field(default=3.0, gt=0)

    @field_validator("horizons")
    @classmethod
    def _horizons_increase(cls, value: tuple[int, ...]) -> tuple[int, ...]:
        if not value or value[0] < 1 or any(b <= a for a, b in pairwise(value)):
            msg = "horizons must be a non-empty, strictly increasing tuple of positive bar counts"
            raise ValueError(msg)
        return value


class OutcomeTable(NamedTuple):
    """Outcomes per anchor (rows) and horizon (columns)."""

    complete: NDArray[np.bool_]
    forward_return: Floats
    forward_atr: Floats
    direction: Ints
    max_up_atr: Floats
    max_down_atr: Floats
    long_barrier: Ints
    long_barrier_bars: NDArray[np.int32]
    long_r: Floats
    short_barrier: Ints
    short_barrier_bars: NDArray[np.int32]
    short_r: Floats


def _first_true(mask: NDArray[np.bool_]) -> tuple[NDArray[np.bool_], NDArray[np.intp]]:
    return mask.any(axis=1), mask.argmax(axis=1)


def _barrier(
    hit_target: NDArray[np.bool_], hit_stop: NDArray[np.bool_]
) -> tuple[Ints, NDArray[np.int32]]:
    has_t, first_t = _first_true(hit_target)
    has_s, first_s = _first_true(hit_stop)
    stop_wins = has_s & (~has_t | (first_s <= first_t))
    target_wins = has_t & ~stop_wins
    result = np.zeros(hit_target.shape[0], dtype=np.int8)
    bars = np.zeros(hit_target.shape[0], dtype=np.int32)
    result[stop_wins], bars[stop_wins] = -1, first_s[stop_wins] + 1
    result[target_wins], bars[target_wins] = 1, first_t[target_wins] + 1
    return result, bars


def compute_outcomes(  # noqa: PLR0917 - OHLC arrays then anchors, mirrors the indicator API
    high: ArrayLike,
    low: ArrayLike,
    close: ArrayLike,
    atr: ArrayLike,
    ends: ArrayLike,
    config: OutcomeConfig | None = None,
) -> OutcomeTable:
    """Outcomes after each anchor bar index in ``ends`` (bars up to ``e + h`` are read, no more)."""
    cfg = config or OutcomeConfig()
    h_arr, l_arr, c_arr, a_arr = (np.asarray(x, dtype=np.float64) for x in (high, low, close, atr))
    if not (h_arr.shape == l_arr.shape == c_arr.shape == a_arr.shape and h_arr.ndim == 1):
        msg = "high, low, close and atr must be 1-D arrays of the same length"
        raise ValueError(msg)
    anchors = np.asarray(ends, dtype=np.intp)
    n = c_arr.size
    if anchors.size and (anchors.min() < 0 or anchors.max() >= n):
        msg = f"anchor index outside 0..{n - 1}"
        raise ValueError(msg)

    shape = (anchors.size, len(cfg.horizons))
    complete = np.zeros(shape, dtype=bool)
    nan = np.full(shape, np.nan)
    fwd_ret, fwd_atr, up, down, long_r, short_r = (nan.copy() for _ in range(6))
    direction = np.zeros(shape, dtype=np.int8)
    long_bar, short_bar = np.zeros(shape, dtype=np.int8), np.zeros(shape, dtype=np.int8)
    long_n, short_n = np.zeros(shape, dtype=np.int32), np.zeros(shape, dtype=np.int32)

    ref_all = c_arr[anchors]
    atr_all = a_arr[anchors]
    stop, target = cfg.stop_atr, cfg.target_atr
    for col, h in enumerate(cfg.horizons):
        ok = (anchors + h < n) & np.isfinite(atr_all) & (atr_all > 0) & np.isfinite(ref_all)
        if not ok.any():
            continue
        idx = anchors[ok]
        ref, a = ref_all[ok], atr_all[ok]
        win_h = sliding_window_view(h_arr, h)[idx + 1]
        win_l = sliding_window_view(l_arr, h)[idx + 1]
        end_close = c_arr[idx + h]

        complete[ok, col] = True
        fwd_ret[ok, col] = end_close / ref - 1.0
        move = (end_close - ref) / a
        fwd_atr[ok, col] = move
        thr = cfg.neutral_threshold_atr
        direction[ok, col] = np.where(move >= thr, 1, np.where(move <= -thr, -1, 0))
        up[ok, col] = np.maximum(win_h.max(axis=1) - ref, 0.0) / a
        down[ok, col] = np.maximum(ref - win_l.min(axis=1), 0.0) / a

        lb, ln = _barrier(win_h >= (ref + target * a)[:, None], win_l <= (ref - stop * a)[:, None])
        sb, sn = _barrier(win_l <= (ref - target * a)[:, None], win_h >= (ref + stop * a)[:, None])
        long_bar[ok, col], long_n[ok, col] = lb, ln
        short_bar[ok, col], short_n[ok, col] = sb, sn
        mark_long = (end_close - ref) / (stop * a)
        long_r[ok, col] = np.where(lb == 1, target / stop, np.where(lb == -1, -1.0, mark_long))
        short_r[ok, col] = np.where(sb == 1, target / stop, np.where(sb == -1, -1.0, -mark_long))

    return OutcomeTable(
        complete,
        fwd_ret,
        fwd_atr,
        direction,
        up,
        down,
        long_bar,
        long_n,
        long_r,
        short_bar,
        short_n,
        short_r,
    )
