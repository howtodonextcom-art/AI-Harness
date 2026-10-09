"""Event detectors for Batch A (H07-H10): causal, closed-bar, one pre-registered rule each.

Every detector reads only bars up to and including the decision bar's close; an event's decision
index is the bar whose close completes the rule, and the label starts at the NEXT bar's open. Events
on days excluded by the clock-safety mask are dropped (and counted), never shifted.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from zoneinfo import ZoneInfo

import numpy as np
import polars as pl
from numpy.typing import NDArray

from xau_edge.features import indicators as ind
from xau_edge.research_v2.frame import H1Frame

LONDON = ZoneInfo("Europe/London")
NEW_YORK = ZoneInfo("America/New_York")
HOUR_US = 3_600_000_000
MIN_DAY_BARS = 12
ASIA_START_HOUR, ASIA_END_HOUR = 0, 7
MIN_ASIA_BARS = 5
M_BARS = 3
RATIO_WINDOW = 120


@dataclass(frozen=True)
class EventSet:
    """Decision bars and directions of one variant (before outcome lookup)."""

    name: str
    decision: NDArray[np.int64]
    direction: NDArray[np.int64]
    level: list[str] = field(default_factory=list)
    excluded_unsafe: int = 0

    @property
    def n(self) -> int:
        return int(self.decision.size)


def _contiguous(f: H1Frame, a: int, b: int) -> bool:
    """No data gap longer than 90 minutes between bar a and bar b."""
    return bool(np.all(np.diff(f.t[a : b + 1]) <= 90 * 60 * 1_000_000)) if b > a else True


Levels = tuple[NDArray[np.float64], NDArray[np.float64], NDArray[np.bool_]]


def prior_day_levels(f: H1Frame) -> Levels:
    """Previous trading day's high and low per bar, plus whether that day is clock-unsafe."""
    hi = np.full(f.n, np.nan)
    lo = np.full(f.n, np.nan)
    unsafe = np.zeros(f.n, dtype=bool)
    keys, start = np.unique(f.day, return_index=True)
    ends = np.append(start[1:], f.n)
    prev: tuple[float, float, bool] | None = None
    for s, e in zip(start, ends, strict=True):
        if prev is not None:
            hi[s:e], lo[s:e], unsafe[s:e] = prev[0], prev[1], prev[2]
        if e - s >= MIN_DAY_BARS:
            prev = (float(f.h[s:e].max()), float(f.low[s:e].min()), bool(f.unsafe_day[s:e].any()))
    del keys
    return hi, lo, unsafe


def asia_levels(f: H1Frame) -> Levels:
    """Asia range (UTC 00:00-07:00) high and low, available from the 07:00 bar of that date."""
    hi = np.full(f.n, np.nan)
    lo = np.full(f.n, np.nan)
    unsafe = np.zeros(f.n, dtype=bool)
    dates, start = np.unique(f.utc_date, return_index=True)
    ends = np.append(start[1:], f.n)
    for s, e in zip(start, ends, strict=True):
        hours = f.utc_hour[s:e]
        in_range = (hours >= ASIA_START_HOUR) & (hours < ASIA_END_HOUR)
        if in_range.sum() < MIN_ASIA_BARS:
            continue
        idx = np.arange(s, e)[in_range]
        later = np.arange(s, e)[hours >= ASIA_END_HOUR]
        hi[later] = f.h[idx].max()
        lo[later] = f.low[idx].min()
        unsafe[later] = bool(f.unsafe_day[idx].any())
    del dates
    return hi, lo, unsafe


def _sweeps(  # noqa: PLR0912, PLR0917
    f: H1Frame,
    name: str,
    mode: str,
    eps: float,
    scope: NDArray[np.int64],
    levels: tuple[
        tuple[str, NDArray[np.float64], NDArray[np.bool_]],
        tuple[str, NDArray[np.float64], NDArray[np.bool_]],
    ],
) -> EventSet:
    decisions: list[int] = []
    directions: list[int] = []
    names: list[str] = []
    excluded = 0
    done: set[tuple[str, int]] = set()
    for side, (lname, lvl, lvl_unsafe) in zip((+1, -1), levels, strict=True):
        for b in range(f.n):
            level = lvl[b]
            if not np.isfinite(level) or (lname, int(scope[b])) in done:
                continue
            breach = f.h[b] > level if side > 0 else f.low[b] < level
            if not breach:
                continue
            done.add((lname, int(scope[b])))
            if f.unsafe_day[b] or lvl_unsafe[b]:
                excluded += 1
                continue
            hit: int | None = None
            if mode == "reject":
                for k in range(b, min(b + M_BARS, f.n)):
                    if not np.isfinite(f.atr[k]) or not _contiguous(f, b, k):
                        break
                    inside = (
                        f.c[k] < level - eps * f.atr[k]
                        if side > 0
                        else f.c[k] > level + eps * f.atr[k]
                    )
                    if inside:
                        hit = k
                        break
                direction = -side
            else:
                k0 = b + 1
                last = k0 + M_BARS
                if last < f.n and np.isfinite(f.atr[k0]) and _contiguous(f, b, last):
                    first_ok = (
                        f.c[k0] > level + eps * f.atr[k0]
                        if side > 0
                        else f.c[k0] < level - eps * f.atr[k0]
                    )
                    held = all(
                        (f.c[j] > level) if side > 0 else (f.c[j] < level)
                        for j in range(k0 + 1, last + 1)
                    )
                    if first_ok and held:
                        hit = last
                direction = side
            if hit is None:
                continue
            if f.unsafe_day[hit]:
                excluded += 1
                continue
            decisions.append(hit)
            directions.append(direction)
            names.append(lname)
    order = np.argsort(decisions, kind="stable") if decisions else np.array([], dtype=np.int64)
    return EventSet(
        name,
        np.asarray(decisions, dtype=np.int64)[order],
        np.asarray(directions, dtype=np.int64)[order],
        [names[i] for i in order],
        excluded,
    )


def sweep_events(f: H1Frame, level_set: str, mode: str, eps: float) -> EventSet:
    """H07 (``reject``) or H08 (``accept``) events for ``PD`` or ``ASIA`` levels."""
    if mode not in {"reject", "accept"} or level_set not in {"PD", "ASIA"}:
        msg = "mode is reject|accept and level_set is PD|ASIA"
        raise ValueError(msg)
    if level_set == "PD":
        hi, lo, un = prior_day_levels(f)
        scope = f.day
        levels = (("PDH", hi, un), ("PDL", lo, un))
    else:
        hi, lo, un = asia_levels(f)
        scope = f.utc_date
        levels = (("ASIAH", hi, un), ("ASIAL", lo, un))
    tag = "H07" if mode == "reject" else "H08"
    return _sweeps(f, f"{tag}-{level_set}-e{eps:g}", mode, eps, scope, levels)


def h4_trend(f: H1Frame, h4: pl.DataFrame, lookback: int) -> NDArray[np.int64]:
    """Sign of (close - SMA(lookback)) of the last H4 bar already closed at each H1 decision."""
    close = h4["close"].to_numpy().astype(np.float64)
    opens = h4["timestamp"].dt.epoch("us").to_numpy().astype(np.int64)
    sma = np.asarray(ind.sma(close, lookback), dtype=np.float64)
    sign = np.where(np.isfinite(sma), np.sign(close - sma), 0).astype(np.int64)
    available = opens + 4 * HOUR_US
    close_time = f.t + HOUR_US
    pos = np.searchsorted(available, close_time, side="right") - 1
    out = np.zeros(f.n, dtype=np.int64)
    ok = pos >= 0
    out[ok] = sign[pos[ok]]
    return out


def _local_hour_minute(f: H1Frame, zone: ZoneInfo) -> tuple[NDArray[np.int64], NDArray[np.int64]]:
    ts = pl.Series(f.t).cast(pl.Datetime("us")).dt.replace_time_zone("UTC")
    local = ts.dt.convert_time_zone(str(zone))
    return (
        local.dt.hour().to_numpy().astype(np.int64),
        local.dt.minute().to_numpy().astype(np.int64),
    )


def transition_events(  # noqa: PLR0912
    f: H1Frame, h4: pl.DataFrame, transition: str, tercile: float
) -> EventSet:
    """H09: the last H1 bar before London open (Asia-London) or New York open (London-NY).

    The event needs the close to sit in an outer ``tercile`` zone of the completed session range;
    direction is the H4 trend sign (continuation with the trend from the outer zone it points to,
    fade from the opposite one: both resolve to the trend sign).
    """
    if transition not in {"ASIA_LONDON", "LONDON_NY"}:
        msg = "transition is ASIA_LONDON or LONDON_NY"
        raise ValueError(msg)
    trend = h4_trend(f, h4, 50)
    lh, lm = _local_hour_minute(f, LONDON)
    nh, nm = _local_hour_minute(f, NEW_YORK)
    decisions: list[int] = []
    directions: list[int] = []
    excluded = 0
    seen: set[int] = set()
    for d in range(f.n):
        if transition == "ASIA_LONDON":
            is_decision = lh[d] == 7 and lm[d] == 0
        else:
            is_decision = nh[d] == 7 and nm[d] == 0
        if not is_decision or int(f.utc_date[d]) in seen:
            continue
        seen.add(int(f.utc_date[d]))
        if transition == "ASIA_LONDON":
            start = d
            while (
                start > 0 and f.utc_date[start - 1] == f.utc_date[d] and f.utc_hour[start - 1] >= 0
            ):
                start -= 1
        else:
            start = d
            while (
                start > 0
                and f.utc_date[start - 1] == f.utc_date[d]
                and not (lh[start] == 8 and lm[start] == 0)
            ):
                start -= 1
            if not (lh[start] == 8 and lm[start] == 0):
                continue
        if f.unsafe_day[d] or f.unsafe_day[start]:
            excluded += 1
            continue
        if d - start < 3 or not _contiguous(f, start, d):
            continue
        hi, lo = float(f.h[start : d + 1].max()), float(f.low[start : d + 1].min())
        if hi <= lo or trend[d] == 0:
            continue
        pos = (f.c[d] - lo) / (hi - lo)
        if pos >= 1 - tercile or pos <= tercile:
            decisions.append(d)
            directions.append(int(trend[d]))
    return EventSet(
        f"H09-{transition}-t{tercile:g}",
        np.asarray(decisions, dtype=np.int64),
        np.asarray(directions, dtype=np.int64),
        [transition] * len(decisions),
        excluded,
    )


def volatility_events(f: H1Frame, h4: pl.DataFrame, c_max: float, lookback: int) -> EventSet:
    """H10: ATR14 compression in London hours, first qualifying bar per trading day, trend side."""
    atr = f.atr
    ratio = np.full(f.n, np.nan)
    for d in range(RATIO_WINDOW - 1, f.n):
        window = atr[d - RATIO_WINDOW + 1 : d + 1]
        if np.all(np.isfinite(window)):
            ratio[d] = atr[d] / window.mean()
    lh, _ = _local_hour_minute(f, LONDON)
    in_session = (lh >= 8) & (lh < 17)
    trend = h4_trend(f, h4, lookback)
    decisions: list[int] = []
    directions: list[int] = []
    excluded = 0
    seen: set[int] = set()
    for d in range(f.n):
        if not (np.isfinite(ratio[d]) and ratio[d] <= c_max and in_session[d]) or trend[d] == 0:
            continue
        if int(f.day[d]) in seen:
            continue
        seen.add(int(f.day[d]))
        if f.unsafe_day[d]:
            excluded += 1
            continue
        decisions.append(d)
        directions.append(int(trend[d]))
    return EventSet(
        f"H10-c{c_max:g}-L{lookback}",
        np.asarray(decisions, dtype=np.int64),
        np.asarray(directions, dtype=np.int64),
        ["COMPRESSION"] * len(decisions),
        excluded,
    )
