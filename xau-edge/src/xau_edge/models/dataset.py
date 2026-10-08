"""Model dataset: scale-free features per bar, forward direction labels, usable-row mask.

Row ``i`` is the decision at the CLOSE of bar ``i`` (``decision_time``). Features use bars up to
``i`` only (tests truncate the bars and require identical rows). The label is the direction of the
move over the next ``horizon`` bars in units of ATR (the outcome engine's UP/DOWN/NEUTRAL, coded
0/1/2); it exists only when those bars exist. Every feature is a ratio or an oscillator, so the
matrix does not depend on the price level.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Final

import numpy as np
import polars as pl
from numpy.typing import NDArray

from xau_edge.domain.timeframe import Timeframe
from xau_edge.features.sessions import TradingSession
from xau_edge.outcomes.engine import OutcomeConfig, compute_outcomes
from xau_edge.strategies.context import build_context
from xau_edge.structure.regime import Regime

MODEL_FEATURE_VERSION: Final = "1"
WARMUP_ROWS: Final = 250
"""Rows before every indicator (EMA 200, regime baseline needs more but is optional) is defined."""

_PASSTHROUGH: Final = (
    "ret_1",
    "log_ret_1",
    "ret_5",
    "ret_10",
    "ret_20",
    "adx_14",
    "plus_di_14",
    "minus_di_14",
    "rsi_14",
    "stoch_k",
    "stoch_d",
    "vol_20",
    "range_atr",
    "body_atr",
    "upper_wick_atr",
    "lower_wick_atr",
    "body_range",
    "volume_zscore",
    "volume_change",
    "trend",
    "bos",
    "choch",
    "high_label",
    "low_label",
    "dist_support_atr",
    "dist_resistance_atr",
)
_DERIVED: Final = (
    "close_vs_ema_9",
    "close_vs_ema_20",
    "close_vs_ema_50",
    "close_vs_ema_200",
    "ema_9_vs_20",
    "ema_20_vs_50",
    "macd_atr",
    "macd_signal_atr",
    "macd_hist_atr",
    "atr_rel",
    "bb_pos",
    "bb_width",
    "gap_before",
    "hour_sin",
    "hour_cos",
    "dow_sin",
    "dow_cos",
)
_SESSIONS: Final = tuple(f"session_{s.value}" for s in TradingSession)
_REGIMES: Final = tuple(f"regime_{r.value}" for r in Regime)
FEATURE_NAMES: Final = (*_PASSTHROUGH, *_DERIVED, *_SESSIONS, *_REGIMES)


@dataclass(frozen=True)
class ModelData:
    """Feature matrix, labels and per-row metadata (all arrays share the bar order)."""

    X: NDArray[np.float64]
    y: NDArray[np.int64]
    usable: NDArray[np.bool_]
    timestamp: NDArray[np.object_]
    decision_time: NDArray[np.object_]
    atr: NDArray[np.float64]
    regime: NDArray[np.object_]
    horizon: int


def _derived(ctx: pl.DataFrame) -> pl.DataFrame:
    c = pl.col("close")
    atr = pl.col("atr_14")
    hour = 2 * np.pi * pl.col("hour").cast(pl.Float64) / 24.0
    dow = 2 * np.pi * pl.col("day_of_week").cast(pl.Float64) / 7.0
    width = pl.col("bb_upper") - pl.col("bb_lower")
    return ctx.select(
        (c / pl.col("ema_9") - 1).alias("close_vs_ema_9"),
        (c / pl.col("ema_20") - 1).alias("close_vs_ema_20"),
        (c / pl.col("ema_50") - 1).alias("close_vs_ema_50"),
        (c / pl.col("ema_200") - 1).alias("close_vs_ema_200"),
        (pl.col("ema_9") / pl.col("ema_20") - 1).alias("ema_9_vs_20"),
        (pl.col("ema_20") / pl.col("ema_50") - 1).alias("ema_20_vs_50"),
        (pl.col("macd") / atr).alias("macd_atr"),
        (pl.col("macd_signal") / atr).alias("macd_signal_atr"),
        (pl.col("macd_hist") / atr).alias("macd_hist_atr"),
        (atr / c).alias("atr_rel"),
        pl.when(width > 0).then((c - pl.col("bb_middle")) / width).alias("bb_pos"),
        (width / pl.col("bb_middle")).alias("bb_width"),
        pl.col("gap_before").cast(pl.Float64).alias("gap_before"),
        hour.sin().alias("hour_sin"),
        hour.cos().alias("hour_cos"),
        dow.sin().alias("dow_sin"),
        dow.cos().alias("dow_cos"),
    )


def _one_hot(values: pl.Series, prefix: str, labels: tuple[str, ...]) -> pl.DataFrame:
    return pl.DataFrame(
        {name: (values == name.removeprefix(f"{prefix}_")).cast(pl.Float64) for name in labels}
    )


def build_model_data(
    bars: pl.DataFrame, timeframe: Timeframe, *, horizon: int, neutral_atr: float = 0.5
) -> ModelData:
    """Build features and labels for every bar of a validated, sorted bar frame."""
    if horizon < 1:
        msg = f"horizon must be >= 1, got {horizon}"
        raise ValueError(msg)
    ctx = build_context(bars, timeframe)
    numeric = ctx.select(
        [pl.col(name).cast(pl.Float64) for name in _PASSTHROUGH if name in ctx.columns]
    )
    frame = pl.concat(
        [
            numeric,
            _derived(ctx),
            _one_hot(ctx["trading_session"], "session", _SESSIONS),
            _one_hot(ctx["regime"].fill_null("UNKNOWN"), "regime", _REGIMES),
        ],
        how="horizontal",
    ).select(FEATURE_NAMES)
    x = frame.to_numpy(allow_copy=True).astype(np.float64)
    x[~np.isfinite(x)] = np.nan

    atr = ctx["atr_14"].fill_null(float("nan")).to_numpy()
    high, low, close = (bars[k].to_numpy() for k in ("high", "low", "close"))
    n = bars.height
    table = compute_outcomes(
        high,
        low,
        close,
        atr,
        np.arange(n),
        OutcomeConfig(horizons=(horizon,), neutral_threshold_atr=neutral_atr),
    )
    complete = table.complete[:, 0]
    y = np.where(complete, table.direction[:, 0].astype(np.int64) + 1, -1)
    usable = complete & (np.arange(n) >= WARMUP_ROWS)
    return ModelData(
        X=x,
        y=y,
        usable=usable,
        timestamp=np.array(bars["timestamp"].to_list(), dtype=object),
        decision_time=np.array(ctx["available_at"].to_list(), dtype=object),
        atr=atr,
        regime=np.array(ctx["regime"].to_list(), dtype=object),
        horizon=horizon,
    )


def decision_time_before(data: ModelData, moment: datetime) -> int:
    """Number of rows whose decision time is strictly before ``moment``."""
    return int(sum(1 for t in data.decision_time if t < moment))
