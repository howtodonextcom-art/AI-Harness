"""Synthetic H1 data for the V2 runner tests: Sunday 18:00 NY to Friday 16:00 NY, no 17:00 hour."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import numpy as np
import polars as pl

from xau_edge.research_v2.frame import H1Frame, build_frame

NY = ZoneInfo("America/New_York")


def timestamps(year: int, weeks: int) -> list[datetime]:
    monday = datetime(year, 1, 1, tzinfo=UTC)
    monday += timedelta(days=(7 - monday.weekday()) % 7)
    out: list[datetime] = []
    for w in range(weeks):
        ny_monday = (monday + timedelta(weeks=w)).replace(hour=12).astimezone(NY)
        cur = (ny_monday.replace(hour=0, minute=0) - timedelta(days=1)).replace(hour=18)
        end = ny_monday.replace(hour=0, minute=0) + timedelta(days=4, hours=17)
        while cur < end:
            if cur.hour != 17:
                out.append(cur.astimezone(UTC))
            cur += timedelta(hours=1)
    return out


def random_walk(year: int = 2023, weeks: int = 20, seed: int = 1, vol: float = 2.0) -> pl.DataFrame:
    stamps = timestamps(year, weeks)
    rng = np.random.default_rng(seed)
    n = len(stamps)
    steps = rng.normal(0, vol, n)
    close = 2000 + np.cumsum(steps)
    open_ = np.concatenate([[2000.0], close[:-1]])
    high = np.maximum(open_, close) + np.abs(rng.normal(0, vol / 2, n))
    low = np.minimum(open_, close) - np.abs(rng.normal(0, vol / 2, n))
    return pl.DataFrame(
        {
            "timestamp": pl.Series(stamps, dtype=pl.Datetime("us", "UTC")),
            "open": open_,
            "high": high,
            "low": low,
            "close": close,
            "spread": np.full(n, 20, dtype=np.int64),
        }
    )


def frame(df: pl.DataFrame, bad_years: set[int] | None = None) -> H1Frame:
    return build_frame(df, bad_years or set())


def hand_bars(
    rows: Sequence[tuple[float, float, float, float]], start_atr_warmup: int = 20
) -> pl.DataFrame:
    """Warm-up bars with a steady 2.0 range, then the given (o, h, l, c) rows."""
    stamps = timestamps(2023, 2)[: start_atr_warmup + len(rows)]
    o, h, low, c = [], [], [], []
    for i in range(start_atr_warmup):
        o.append(2000.0)
        h.append(2001.0)
        low.append(1999.0)
        c.append(2000.0)
        del i
    for row in rows:
        o.append(row[0])
        h.append(row[1])
        low.append(row[2])
        c.append(row[3])
    return pl.DataFrame(
        {
            "timestamp": pl.Series(stamps, dtype=pl.Datetime("us", "UTC")),
            "open": o,
            "high": h,
            "low": low,
            "close": c,
            "spread": np.full(len(stamps), 20, dtype=np.int64),
        }
    )
