"""Rule-based market regime classification (rules and thresholds documented in ADR-0012).

Per bar, first matching rule wins:

1. ``SHOCK``: bar range >= ``shock_range_atr`` x the PREVIOUS bar's ATR (the bar's own ATR is
   excluded so the shock cannot mask itself).
2. ``HIGH_VOLATILITY``: ATR / median ATR of the previous ``vol_window`` bars >= ``high_vol_ratio``.
3. ``TREND_UP`` / ``TREND_DOWN``: ADX >= ``adx_trend``; direction from +DI versus -DI.
4. ``LOW_VOLATILITY``: the same ratio <= ``low_vol_ratio``.
5. ``RANGE``: otherwise.

Thresholds are set a priori (conventional ADX 25; ratios of 1.5 and 1/1.5), not fitted to data, and
must not be tuned on the evaluation period. A bar is ``None`` (unknown) until its inputs exist and
at least ``min_history`` earlier ATR values are available. The volatility baseline uses only
earlier bars, so labels never change when later bars arrive.
"""

from __future__ import annotations

import warnings
from enum import StrEnum

import numpy as np
from numpy.lib.stride_tricks import sliding_window_view
from numpy.typing import ArrayLike, NDArray
from pydantic import BaseModel, ConfigDict, Field, model_validator


class Regime(StrEnum):
    """Regime labels."""

    TREND_UP = "TREND_UP"
    TREND_DOWN = "TREND_DOWN"
    RANGE = "RANGE"
    HIGH_VOLATILITY = "HIGH_VOLATILITY"
    LOW_VOLATILITY = "LOW_VOLATILITY"
    SHOCK = "SHOCK"


class RegimeConfig(BaseModel):
    """Thresholds of the regime rules."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    adx_trend: float = Field(default=25.0, gt=0)
    vol_window: int = Field(default=500, ge=2)
    min_history: int = Field(default=100, ge=2)
    high_vol_ratio: float = Field(default=1.5)
    low_vol_ratio: float = Field(default=0.67, gt=0)
    shock_range_atr: float = Field(default=3.0, gt=0)

    @model_validator(mode="after")
    def _ordered(self) -> RegimeConfig:
        if self.high_vol_ratio <= 1.0:
            msg = "high_vol_ratio must be > 1"
            raise ValueError(msg)
        if self.low_vol_ratio >= 1.0:
            msg = "low_vol_ratio must be < 1"
            raise ValueError(msg)
        if self.min_history > self.vol_window:
            msg = "min_history must be <= vol_window"
            raise ValueError(msg)
        return self


_CHUNK = 4096


def _past_median(values: NDArray[np.float64], window: int, min_history: int) -> NDArray[np.float64]:
    """Median of the ``window`` values before each index (current excluded), NaN-aware."""
    n = values.size
    out = np.full(n, np.nan)
    padded = np.concatenate([np.full(window, np.nan), values])
    view = sliding_window_view(padded, window)[:n]
    for start in range(0, n, _CHUNK):
        block = view[start : start + _CHUNK]
        counts = (~np.isnan(block)).sum(axis=1)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            med = np.nanmedian(block, axis=1)
        med[counts < min_history] = np.nan
        out[start : start + _CHUNK] = med
    return out


def classify_regime(
    *,
    adx: ArrayLike,
    plus_di: ArrayLike,
    minus_di: ArrayLike,
    atr: ArrayLike,
    high: ArrayLike,
    low: ArrayLike,
    config: RegimeConfig | None = None,
) -> NDArray[np.object_]:
    """Return one regime label (``str`` value of ``Regime``) or ``None`` per bar."""
    cfg = config or RegimeConfig()
    arrays = [np.asarray(x, dtype=np.float64) for x in (adx, plus_di, minus_di, atr, high, low)]
    a_adx, a_plus, a_minus, a_atr, a_high, a_low = arrays
    sizes = {a.size for a in arrays}
    if len(sizes) != 1 or any(a.ndim != 1 for a in arrays):
        msg = f"all inputs must be 1-D with the same length, got sizes {sorted(sizes)}"
        raise ValueError(msg)
    n = a_adx.size
    baseline = _past_median(a_atr, cfg.vol_window, cfg.min_history)
    with np.errstate(divide="ignore", invalid="ignore"):
        ratio = np.where(baseline > 0, a_atr / baseline, np.nan)
    prev_atr = np.concatenate([[np.nan], a_atr[:-1]])
    bar_range = a_high - a_low

    out = np.full(n, None, dtype=object)
    known = ~np.isnan(a_adx) & ~np.isnan(a_plus) & ~np.isnan(a_minus) & ~np.isnan(ratio)
    known &= (prev_atr > 0) & ~np.isnan(bar_range)
    shock = known & (bar_range >= cfg.shock_range_atr * prev_atr)
    high_vol = known & (ratio >= cfg.high_vol_ratio)
    trending = known & (a_adx >= cfg.adx_trend)
    low_vol = known & (ratio <= cfg.low_vol_ratio)

    out[known] = Regime.RANGE.value
    out[low_vol] = Regime.LOW_VOLATILITY.value
    out[trending & (a_plus > a_minus)] = Regime.TREND_UP.value
    out[trending & (a_minus > a_plus)] = Regime.TREND_DOWN.value
    out[high_vol] = Regime.HIGH_VOLATILITY.value
    out[shock] = Regime.SHOCK.value
    return out
