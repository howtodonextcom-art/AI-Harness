"""Detection of the daily pseudo-bar found in the shared XAUUSD store (2012-06-26 .. 2021-01-20).

One bar per trading day, stamped at the rollover minute (21:00 UTC in summer, 22:00 in winter), with
spread 0 and a day-sized tick volume, carries the OHLC of the FOLLOWING trading session (see
``reports/V2_DATA_PROVENANCE_FORENSIC_REPORT.md``). Any consumer that treats it as a closed intraday
bar looks 24 hours ahead. The same bar is present in M1, M5, M15, M30 and H1, and is merged into the
H4 bar that contains it.

This module only DETECTS (and can drop) those bars from a copy of a frame. It never edits the store and
never fabricates data; H4 cannot be repaired by dropping, it has to be re-fetched or rebuilt.

A normal first bar after the daily break also has spread 0 but a few thousand ticks; the pseudo-bar has
36 000 to 190 000, hence the volume floor.
"""

from __future__ import annotations

import numpy as np
import polars as pl

ROLLOVER_HOURS = (21, 22)
MIN_TICK_VOLUME = 20_000.0
MEDIAN_MULTIPLE = 20.0


def pseudo_bar_mask(frame: pl.DataFrame) -> np.ndarray:
    """True for the pseudo-bars of ``frame`` (columns: timestamp, spread, tick_volume)."""
    if frame.height == 0:
        return np.zeros(0, dtype=bool)
    vol = frame["tick_volume"].to_numpy()
    floor = max(MIN_TICK_VOLUME, MEDIAN_MULTIPLE * max(float(np.median(vol)), 1.0))
    hour = frame["timestamp"].dt.hour().to_numpy()
    minute = frame["timestamp"].dt.minute().to_numpy()
    spread = frame["spread"].to_numpy()
    mask = np.isin(hour, ROLLOVER_HOURS) & (minute == 0) & (spread == 0) & (vol >= floor)
    return np.asarray(mask, dtype=bool)


def strip_pseudo_bars(frame: pl.DataFrame) -> tuple[pl.DataFrame, int]:
    """A copy of ``frame`` without the pseudo-bars, and how many were dropped."""
    mask = pseudo_bar_mask(frame)
    return frame.filter(pl.Series(~mask)), int(mask.sum())


class DataDefectError(RuntimeError):
    """A month of bars contains pseudo-bars: no result computed on it may be used."""


def require_clean(frame: pl.DataFrame, label: str) -> None:
    """Raise ``DataDefectError`` when ``frame`` holds pseudo-bars (research pipelines call this first)."""
    n = int(pseudo_bar_mask(frame).sum())
    if n:
        msg = f"{label}: {n} daily pseudo-bar(s) (next-day OHLC at the rollover): the data is defective"
        raise DataDefectError(msg)
