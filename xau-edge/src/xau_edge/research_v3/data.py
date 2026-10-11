"""Read-only loaders for the V3 runners with a hard partition guard.

Test-H (2022-01-01..2025-04-30) and Holdout (2026-05-01..2026-10-07) are protected. Stage 1 and
Validation never need a month at or after 2022-01, so any request that would read such a month
raises before a file is opened. Opening a protected split goes through ``research_v2.guards`` and a
committed freeze record, never through this module.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import polars as pl

PROTECTED_FROM = date(2022, 1, 1)
ROOT = Path(__file__).resolve().parents[3]
MARKET = ROOT / "data" / "market"


class ProtectedDataError(RuntimeError):
    """A loader was asked for data inside a protected split."""


def _months(start: date, end: date) -> list[str]:
    out: list[str] = []
    y, m = start.year, start.month
    while (y, m) <= (end.year, end.month):
        out.append(f"{y:04d}-{m:02d}")
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


def load_bars(symbol: str, timeframe: str, start: date, end: date) -> pl.DataFrame:
    """Bars of ``[start-month, end-month]`` as stored (sorted, de-duplicated by timestamp)."""
    if end >= PROTECTED_FROM:
        raise ProtectedDataError(f"{symbol} {timeframe} up to {end} reaches a protected split")
    files = [MARKET / symbol / timeframe / f"{mo}.parquet" for mo in _months(start, end)]
    present = [f for f in files if f.exists()]
    if not present:
        raise FileNotFoundError(f"no {symbol} {timeframe} files for {start}..{end}")
    cols = ["timestamp", "open", "high", "low", "close", "spread"]
    df = pl.concat([pl.read_parquet(f, columns=cols) for f in present], how="vertical_relaxed")
    return df.unique(subset=["timestamp"], keep="first").sort("timestamp")
