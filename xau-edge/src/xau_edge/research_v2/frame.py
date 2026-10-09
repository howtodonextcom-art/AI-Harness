"""H1 research frame for Edge Program V2: arrays, trading-day keys and the clock-safety mask.

Built from the stored research dataset exactly as it is (ADR-0005: reported, never repaired). The
only exclusion rule is the declared clock-safety mask: in years whose broker clock is NOT
certified (``docs/research/edge-program-v2/clock-certificate.json``), days inside the US/EU
daylight-saving mismatch interval are excluded from event creation, because the stored UTC time of
those bars is one hour off. Nothing is shifted or repaired.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import polars as pl
from numpy.typing import NDArray

from xau_edge.features import indicators as ind

NEW_YORK = ZoneInfo("America/New_York")
ATHENS = ZoneInfo("Europe/Athens")
ROLLOVER_HOUR = 17
TYPICAL_OFFSET_DIFF_HOURS = 7.0
ATR_PERIOD = 14
EPOCH = date(1970, 1, 1)


@dataclass(frozen=True)
class H1Frame:
    """Aligned arrays for the bars of one analysis window (including warm-up)."""

    t: NDArray[np.int64]
    """Bar-open time, microseconds since the epoch, UTC."""
    o: NDArray[np.float64]
    h: NDArray[np.float64]
    low: NDArray[np.float64]
    c: NDArray[np.float64]
    spread: NDArray[np.float64]
    atr: NDArray[np.float64]
    day: NDArray[np.int64]
    """Trading-day key: days since the epoch of (New York time - 17h)."""
    utc_date: NDArray[np.int64]
    utc_hour: NDArray[np.int64]
    year: NDArray[np.int64]
    unsafe_day: NDArray[np.bool_]
    """True for bars of a trading day inside an uncertified year's DST mismatch interval."""

    @property
    def n(self) -> int:
        return int(self.t.size)


def uncertified_years(certificate: Path) -> set[int]:
    """Years the clock certificate does not certify (missing file means every year)."""
    try:
        raw = json.loads(certificate.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return set(range(2000, 2100))
    years = raw.get("years", {}) if isinstance(raw, dict) else {}
    return {int(y) for y, v in years.items() if not (isinstance(v, dict) and v.get("certified"))}


def _mismatch_days(days: list[date]) -> set[date]:
    """Dates where New York and Athens daylight saving differ (offset gap other than 7 hours)."""
    bad: set[date] = set()
    for d in days:
        noon = datetime(d.year, d.month, d.day, 12, tzinfo=UTC)
        ny = noon.astimezone(NEW_YORK).utcoffset()
        eu = noon.astimezone(ATHENS).utcoffset()
        if ny is None or eu is None:
            continue
        if (eu - ny).total_seconds() / 3600 != TYPICAL_OFFSET_DIFF_HOURS:
            bad.add(d)
    return bad


def build_frame(bars: pl.DataFrame, bad_years: set[int]) -> H1Frame:
    """Arrays from ``timestamp, open, high, low, close, spread`` (sorted, UTC)."""
    ts = bars["timestamp"]
    h, lo, c = (bars[k].to_numpy().astype(np.float64) for k in ("high", "low", "close"))
    atr = np.asarray(ind.atr(h, lo, c, ATR_PERIOD), dtype=np.float64)
    ny = ts.dt.convert_time_zone("America/New_York").dt.replace_time_zone(None)
    key = (ny - timedelta(hours=ROLLOVER_HOUR)).dt.date().dt.epoch("d").to_numpy().astype(np.int64)
    utc_date = ts.dt.date().dt.epoch("d").to_numpy().astype(np.int64)
    utc_hour = ts.dt.hour().to_numpy().astype(np.int64)
    year = ts.dt.year().to_numpy().astype(np.int64)
    dates = [EPOCH + timedelta(days=int(d)) for d in np.unique(utc_date)]
    mismatch = {(d - EPOCH).days for d in _mismatch_days(dates)}
    bad_mask_date = np.isin(utc_date, list(mismatch)) & np.isin(year, list(bad_years))
    # a trading day is unsafe if any of its bars is unsafe
    unsafe_keys = np.unique(key[bad_mask_date])
    unsafe_day = np.isin(key, unsafe_keys)
    return H1Frame(
        t=ts.dt.epoch("us").to_numpy().astype(np.int64),
        o=bars["open"].to_numpy().astype(np.float64),
        h=h,
        low=lo,
        c=c,
        spread=bars["spread"].to_numpy().astype(np.float64),
        atr=atr,
        day=key,
        utc_date=utc_date,
        utc_hour=utc_hour,
        year=year,
        unsafe_day=unsafe_day,
    )


def weekday_of_key(key: NDArray[np.int64]) -> NDArray[np.int64]:
    """Monday = 0 for a day key (epoch day 0 is a Thursday)."""
    return (key + 3) % 7
