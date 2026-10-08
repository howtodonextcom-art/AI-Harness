"""Scale-free, causal pattern representation (brief section 14).

Each bar becomes a vector of ATR-normalised quantities, so windows from different price levels and
volatility regimes are comparable and no global statistic (which could leak the future) is needed:

``ret_atr`` close-to-close change, ``body_atr`` signed body, ``upper_wick_atr``, ``lower_wick_atr``,
``range_atr`` (all divided by the ATR of the same bar, known at its close) and ``volume_z`` (tick
volume z-score over the previous ``volume_window`` bars including this one).
"""

from __future__ import annotations

from typing import Final

import numpy as np
import polars as pl
from numpy.lib.stride_tricks import sliding_window_view
from numpy.typing import NDArray

from xau_edge.domain.timeframe import Timeframe
from xau_edge.features import indicators as ind
from xau_edge.features.feature_set import check_bars
from xau_edge.features.volume import volume_zscore

PATTERN_COLUMNS: Final = (
    "ret_atr",
    "body_atr",
    "upper_wick_atr",
    "lower_wick_atr",
    "range_atr",
    "volume_z",
)

Floats = NDArray[np.float64]


def pattern_values(bars: pl.DataFrame, *, atr_period: int = 14, volume_window: int = 20) -> Floats:
    """Return a ``(bars, 6)`` array; warm-up rows and zero-ATR bars are ``NaN``."""
    check_bars(bars)
    o, h, lo, c = (bars[k].to_numpy() for k in ("open", "high", "low", "close"))
    volume = bars["tick_volume"].to_numpy().astype(np.float64)
    atr = ind.atr(h, lo, c, atr_period)
    safe = np.where(atr > 0, atr, np.nan)
    prev_close = np.concatenate([[np.nan], c[:-1]])
    columns = [
        (c - prev_close) / safe,
        (c - o) / safe,
        (h - np.maximum(o, c)) / safe,
        (np.minimum(o, c) - lo) / safe,
        (h - lo) / safe,
        volume_zscore(volume, volume_window),
    ]
    return np.column_stack(columns)


def pattern_frame(
    bars: pl.DataFrame,
    timeframe: Timeframe,
    *,
    atr_period: int = 14,
    volume_window: int = 20,
) -> pl.DataFrame:
    """Pattern vectors as a frame with ``timestamp`` and ``available_at``."""
    values = pattern_values(bars, atr_period=atr_period, volume_window=volume_window)
    ts = bars["timestamp"]
    cols = [
        pl.Series(name, values[:, i], dtype=pl.Float64, nan_to_null=True)
        for i, name in enumerate(PATTERN_COLUMNS)
    ]
    return pl.DataFrame([ts, ts.dt.offset_by(f"{timeframe.minutes}m").alias("available_at"), *cols])


def window_view(values: Floats, window: int) -> Floats:
    """Zero-copy view of all length-``window`` windows: shape ``(windows, window, features)``."""
    if window < 1:
        msg = f"window must be >= 1, got {window}"
        raise ValueError(msg)
    if values.shape[0] < window:
        return np.empty((0, window, values.shape[1]))
    view = sliding_window_view(values, window, axis=0)  # (M, F, W)
    return np.swapaxes(view, 1, 2)


def window_validity(values: Floats, window: int) -> NDArray[np.bool_]:
    """``True`` for windows whose every value is finite (window ``j`` covers rows ``j..j+W-1``)."""
    if window < 1:
        msg = f"window must be >= 1, got {window}"
        raise ValueError(msg)
    n = values.shape[0]
    if n < window:
        return np.zeros(0, dtype=bool)
    bad = (~np.isfinite(values)).any(axis=1).astype(np.int64)
    csum = np.concatenate([[0], np.cumsum(bad)])
    return np.asarray((csum[window:] - csum[:-window]) == 0, dtype=bool)
