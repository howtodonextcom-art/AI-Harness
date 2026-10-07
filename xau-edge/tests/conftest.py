"""Shared fixtures.

All price data generated here is SYNTHETIC and exists only to exercise code paths.
It carries no market information and must never be used for research conclusions.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import polars as pl
import pytest

from xau_edge.domain.bars import BAR_SCHEMA
from xau_edge.domain.timeframe import Timeframe

# A Monday, so short synthetic runs never touch the weekend closure.
MONDAY = datetime(2025, 3, 3, 0, 0, tzinfo=UTC)


def make_bars(
    n: int = 50,
    timeframe: Timeframe = Timeframe.M15,
    start: datetime = MONDAY,
    base: float = 2000.0,
) -> pl.DataFrame:
    """Return ``n`` internally consistent synthetic bars starting at ``start``."""
    step = timedelta(minutes=timeframe.minutes)
    rows = []
    prev_close = base
    for i in range(n):
        close = base + 0.1 * i
        high = max(prev_close, close) + 0.3
        low = min(prev_close, close) - 0.3
        rows.append(
            {
                "timestamp": start + i * step,
                "open": prev_close,
                "high": high,
                "low": low,
                "close": close,
                "tick_volume": 100 + i,
                "spread": 25,
                "real_volume": None,
            }
        )
        prev_close = close
    return pl.DataFrame(rows, schema=BAR_SCHEMA)


@pytest.fixture
def bars() -> pl.DataFrame:
    return make_bars()
