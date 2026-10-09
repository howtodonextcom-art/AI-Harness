"""Volume semantics and timeframe-normalised activity (trading core sections 4 and 7).

On an OTC CFD feed the MT5 "volume" is normally the NUMBER OF PRICE UPDATES (tick volume), not a
centralised traded quantity. ``detect_volume_type`` decides from the data, and the answer is
carried in the schema (``volume_type``) so tick volume is never silently presented as real volume.
Raw volumes are never compared across timeframes: each timeframe is normalised against its OWN
recent baseline, and only the normalised values are compared. Every function is causal.
"""

from __future__ import annotations

from enum import StrEnum

import numpy as np
from numpy.typing import ArrayLike, NDArray

from xau_edge.features.volume import volume_zscore

Floats = NDArray[np.float64]


class VolumeType(StrEnum):
    """What the volume field of a feed means."""

    TICK_VOLUME = "TICK_VOLUME"
    REAL_VOLUME = "REAL_VOLUME"
    UNKNOWN = "UNKNOWN"


def detect_volume_type(
    tick_volume: ArrayLike, real_volume: ArrayLike | None, *, min_bars: int = 50
) -> VolumeType:
    """TICK_VOLUME when the feed has no real volume at all; otherwise UNKNOWN (never REAL).

    REAL_VOLUME is never inferred from data: a non-zero ``real_volume`` could still be a
    broker-specific counter, so it needs a human verification recorded outside this function.
    """
    ticks = np.asarray(tick_volume, dtype=np.float64)
    if ticks.size < min_bars or not np.isfinite(ticks).all() or (ticks <= 0).all():
        return VolumeType.UNKNOWN
    if real_volume is None:
        return VolumeType.TICK_VOLUME
    real = np.asarray(real_volume, dtype=np.float64)
    real = real[np.isfinite(real)]
    if real.size == 0 or float(np.abs(real).sum()) == 0.0:
        return VolumeType.TICK_VOLUME
    return VolumeType.UNKNOWN


def volume_percentile(volume: ArrayLike, window: int = 100) -> Floats:
    """Share of the previous ``window`` bars (current included) that are <= the current bar."""
    v = np.asarray(volume, dtype=np.float64)
    out = np.full(v.size, np.nan)
    for i in range(window - 1, v.size):
        win = v[i - window + 1 : i + 1]
        out[i] = float(np.mean(win <= v[i]))
    return out


def volume_ratio(volume: ArrayLike, window: int = 20) -> Floats:
    """Current volume over the mean of the PREVIOUS ``window`` bars (current excluded)."""
    v = np.asarray(volume, dtype=np.float64)
    out = np.full(v.size, np.nan)
    for i in range(window, v.size):
        base = float(np.mean(v[i - window : i]))
        out[i] = v[i] / base if base > 0 else np.nan
    return out


def volume_acceleration(zscore: ArrayLike, lag: int = 3) -> Floats:
    """Change of the volume z-score over ``lag`` bars (positive: activity is building up)."""
    z = np.asarray(zscore, dtype=np.float64)
    out = np.full(z.size, np.nan)
    if z.size > lag:
        out[lag:] = z[lag:] - z[:-lag]
    return out


def activity(volume: ArrayLike, *, z_window: int = 20, pct_window: int = 100) -> dict[str, Floats]:
    """The normalised activity features of ONE timeframe."""
    z = volume_zscore(volume, z_window)
    return {
        "zscore": z,
        "percentile": volume_percentile(volume, pct_window),
        "ratio": volume_ratio(volume, z_window),
        "acceleration": volume_acceleration(z),
    }
