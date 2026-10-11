"""F3-USMOM-0930-1400-1500-1645 (F3_us_session_momentum.md + F3_amendment_1.md), frozen 2026-10-11.

Signal s = sign(open M1 14:00 NY - open M1 09:30 NY) on bid; enter at the 15:00 NY open in direction
s, exit at the 16:45 NY open; catastrophic stop 3 ATR(H1, 14) of the H1 bar opening 14:00 NY; R =
that ATR. Exclusions, in counting order: clock-safety mask (amendment A1), holiday / early close
overlapping [09:30, 17:00) NY, a missing anchor bar, M1 coverage below 95% of 09:30-16:44 NY, no
usable ATR, s = 0. No swap (flat before the 17:00 New York rollover).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import numpy as np
import polars as pl
from numpy.typing import NDArray

from xau_edge.features import indicators as ind
from xau_edge.research_v3.execution import GROSS, M1, POINT, scenarios_for_year, simulate
from xau_edge.research_v3.f1 import m1_arrays, trading_day

NEW_YORK = ZoneInfo("America/New_York")
ATHENS = ZoneInfo("Europe/Athens")
OPEN_NY, SIGNAL_NY, ENTRY_NY, EXIT_NY, SESSION_END_NY = (
    time(9, 30),
    time(14, 0),
    time(15, 0),
    time(16, 45),
    time(17, 0),
)
ATR_PERIOD = 14
STOP_ATR = 3.0
WINDOW_MINUTES = 435
MIN_COVERAGE = 0.95
MINUTE_US = 60_000_000


def ny_us(d: date, t: time) -> int:
    return int(datetime.combine(d, t, tzinfo=NEW_YORK).timestamp() * 1e6)


def clock_unsafe(d: date, uncertified: set[int]) -> bool:
    """Amendment A1: uncertified year and New York / Athens offsets not 7 h apart at 12:00 UTC."""
    if d.year not in uncertified:
        return False
    noon = datetime(d.year, d.month, d.day, 12, tzinfo=UTC)
    ny, eu = noon.astimezone(NEW_YORK).utcoffset(), noon.astimezone(ATHENS).utcoffset()
    return ny is None or eu is None or (eu - ny) != timedelta(hours=7)


@dataclass(frozen=True)
class Closures:
    start_us: NDArray[np.int64]
    end_us: NDArray[np.int64]

    @classmethod
    def from_windows(cls, windows: list[tuple[datetime, datetime]]) -> Closures:
        return cls(
            np.array([int(a.timestamp() * 1e6) for a, _ in windows], dtype=np.int64),
            np.array([int(b.timestamp() * 1e6) for _, b in windows], dtype=np.int64),
        )

    def overlaps(self, a: int, b: int) -> bool:
        return bool(((self.start_us < b) & (self.end_us > a)).any())


def _exact(t: NDArray[np.int64], value: int) -> int | None:
    k = int(np.searchsorted(t, value))
    return k if k < t.size and t[k] == value else None


def run(  # noqa: PLR0917
    xau_h1: pl.DataFrame,
    xau_m1: pl.DataFrame,
    start: date,
    end: date,
    closures: Closures,
    uncertified: set[int],
) -> dict[str, Any]:
    """One candidate per New York weekday in [start, end); outcomes on every cost path."""
    ht = xau_h1["timestamp"].dt.epoch("us").to_numpy().astype(np.int64)
    atr = np.asarray(
        ind.atr(
            xau_h1["high"].to_numpy(),
            xau_h1["low"].to_numpy(),
            xau_h1["close"].to_numpy(),
            ATR_PERIOD,
        ),
        dtype=np.float64,
    )
    m1 = m1_arrays(xau_m1)
    counts = dict.fromkeys(
        (
            "weekdays",
            "excluded_clock_mask",
            "excluded_holiday_or_early_close",
            "excluded_missing_anchor",
            "excluded_low_coverage",
            "excluded_no_atr",
            "no_signal_zero_move",
        ),
        0,
    )
    trades: list[dict[str, Any]] = []
    d = start
    while d < end:
        day, d = d, d + timedelta(days=1)
        if day.weekday() >= 5:
            continue
        counts["weekdays"] += 1
        if clock_unsafe(day, uncertified):
            counts["excluded_clock_mask"] += 1
            continue
        if closures.overlaps(ny_us(day, OPEN_NY), ny_us(day, SESSION_END_NY)):
            counts["excluded_holiday_or_early_close"] += 1
            continue
        idx = [_exact(m1.t, ny_us(day, t)) for t in (OPEN_NY, SIGNAL_NY, ENTRY_NY, EXIT_NY)]
        if any(i is None for i in idx):
            counts["excluded_missing_anchor"] += 1
            continue
        i_open, i_sig, e, x = (int(i) for i in idx if i is not None)
        present = int(np.searchsorted(m1.t, ny_us(day, EXIT_NY)) - i_open)
        if present < WINDOW_MINUTES * MIN_COVERAGE:
            counts["excluded_low_coverage"] += 1
            continue
        k = _exact(ht, ny_us(day, SIGNAL_NY))
        if k is None or not np.isfinite(atr[k]) or atr[k] <= 0:
            counts["excluded_no_atr"] += 1
            continue
        move = float(m1.o[i_sig] - m1.o[i_open])
        if move == 0:
            counts["no_signal_zero_move"] += 1
            continue
        trades.append(_trade(m1, (i_open, e, x), int(np.sign(move)), float(atr[k]), day, move))
    return {"counts": counts, "trades": trades}


def _trade(  # noqa: PLR0917
    m1: M1, idx: tuple[int, int, int], direction: int, a: float, day: date, move: float
) -> dict[str, Any]:
    i_open, e, x = idx
    base_sc, pess_sc = scenarios_for_year(day.year)
    sides: dict[int, dict[str, Any]] = {}
    for s in (1, -1):
        g, b, p = (
            simulate(m1, e, x, s, a, STOP_ATR * a, None, sc) for sc in (GROSS, base_sc, pess_sc)
        )
        if g is None or b is None or p is None:
            msg = "the 16:45 bar exists, so every path must be priced"
            raise RuntimeError(msg)
        sides[s] = {"gross": g.r, "base": b.r, "pess": p.r, "fill": b}
    me = sides[direction]
    bf = me["fill"]
    return {
        "ny_date": day.isoformat(),
        "year": day.year,
        "weekday": day.weekday(),
        "move_0930_1400": move,
        "open_0930": float(m1.o[i_open]),
        "direction": direction,
        "atr": a,
        "entry_us": int(m1.t[e]),
        "exit_us": int(m1.t[bf.exit_i]),
        "entry_px": bf.entry_px,
        "exit_px": bf.exit_px,
        "reason": bf.reason,
        "gross_r": me["gross"],
        "base_r": me["base"],
        "pess_r": me["pess"],
        "slip_r": 2 * base_sc.slip_points * POINT / a,
        "long_base_r": sides[1]["base"],
        "short_base_r": sides[-1]["base"],
        "day": trading_day(int(m1.t[e])),
    }


def reference_day(
    bars_ny: dict[str, tuple[float, float, float, float]],
    a: float,
    spread_mult: float,
    slip_points: float,
) -> tuple[int, str, str, float] | None:
    """Oracle on one day's M1 bars keyed by New York "HH:MM": (direction, exit HH:MM, reason, R).

    ``None`` for a missing anchor, low coverage or a zero move. Bars are (open, high, low, spread).
    """
    anchors = ("09:30", "14:00", "15:00", "16:45")
    if any(k not in bars_ny for k in anchors):
        return None
    minutes = [f"{h:02d}:{m:02d}" for h in range(9, 17) for m in range(60)]
    window = [k for k in minutes if "09:30" <= k < "16:45"]
    if sum(k in bars_ny for k in window) < 0.95 * len(window):
        return None
    move = bars_ny["14:00"][0] - bars_ny["09:30"][0]
    if move == 0:
        return None
    s = 1 if move > 0 else -1
    slip = 2 * slip_points * POINT / a
    ask = {k: v[3] * POINT * spread_mult for k, v in bars_ny.items()}
    entry = bars_ny["15:00"][0] + (ask["15:00"] if s == 1 else 0.0)
    stop = entry - s * STOP_ATR * a
    for k in [m for m in minutes if "15:00" <= m < "16:45" and m in bars_ny]:
        o, h, lo, _ = bars_ny[k]
        if s == 1 and lo <= stop:
            px = o if k != "15:00" and o <= stop else stop
            return s, k, "STOP_LOSS", (px - entry) / a - slip
        if s == -1 and h + ask[k] >= stop:
            px = o + ask[k] if k != "15:00" and o + ask[k] >= stop else stop
            return s, k, "STOP_LOSS", (entry - px) / a - slip
    out = bars_ny["16:45"][0] + (0.0 if s == 1 else ask["16:45"])
    return s, "16:45", "TIME_EXIT", s * (out - entry) / a - slip
