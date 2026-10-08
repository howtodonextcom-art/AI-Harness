"""Structure and regime as a frame aligned to the bars (same row index and timing as features)."""

from __future__ import annotations

import numpy as np
import polars as pl
from numpy.typing import NDArray

from xau_edge.domain.timeframe import Timeframe
from xau_edge.features import indicators as ind
from xau_edge.features.feature_set import check_bars
from xau_edge.structure.regime import RegimeConfig, classify_regime
from xau_edge.structure.swings import StructureConfig, analyse_structure


def _f(name: str, values: NDArray[np.float64]) -> pl.Series:
    return pl.Series(name, values, dtype=pl.Float64, nan_to_null=True)


def structure_frame(
    bars: pl.DataFrame,
    timeframe: Timeframe,
    *,
    structure: StructureConfig | None = None,
    regime: RegimeConfig | None = None,
    atr_period: int = 14,
    adx_period: int = 14,
) -> pl.DataFrame:
    """Swings, labels, trend, BOS/CHoCH, support/resistance and regime for each bar.

    Like the feature set, row ``i`` is usable from ``available_at`` (the bar's close) and depends on
    bars ``0..i`` only. Distances to support/resistance are in ATR units (positive by construction).
    """
    check_bars(bars)
    h, lo, c = (bars[k].to_numpy() for k in ("high", "low", "close"))
    s = analyse_structure(h, lo, c, structure)
    atr = ind.atr(h, lo, c, atr_period)
    adx = ind.adx(h, lo, c, adx_period)
    labels = classify_regime(
        adx=adx.adx,
        plus_di=adx.plus_di,
        minus_di=adx.minus_di,
        atr=atr,
        high=h,
        low=lo,
        config=regime,
    )
    ts = bars["timestamp"]
    with np.errstate(divide="ignore", invalid="ignore"):
        dist_support = np.where(atr > 0, (c - s.support) / atr, np.nan)
        dist_resistance = np.where(atr > 0, (s.resistance - c) / atr, np.nan)
    return pl.DataFrame(
        [
            ts,
            ts.dt.offset_by(f"{timeframe.minutes}m").alias("available_at"),
            _f("swing_high", s.last_swing_high),
            _f("swing_low", s.last_swing_low),
            pl.Series("high_label", s.high_label, dtype=pl.Int8),
            pl.Series("low_label", s.low_label, dtype=pl.Int8),
            pl.Series("trend", s.trend, dtype=pl.Int8),
            pl.Series("bos", s.bos, dtype=pl.Int8),
            pl.Series("choch", s.choch, dtype=pl.Int8),
            _f("support", s.support),
            _f("resistance", s.resistance),
            _f("dist_support_atr", dist_support),
            _f("dist_resistance_atr", dist_resistance),
            pl.Series("regime", labels.tolist(), dtype=pl.String),
        ]
    )
