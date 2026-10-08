"""Research-only helpers for the history expansion (edge program, T1.2).

``fetch_back`` walks calendar months backwards from an end instant until the source has returned
nothing for several months in a row; the caller supplies a read-only fetch function, so the module
has no broker dependency. ``daily_from_h1`` builds a research-only daily dataset by resampling H1
bars on the broker's server day (17:00 New York); no ``D1`` member is added to ``Timeframe``.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta

import polars as pl

from xau_edge.domain.bars import empty_bars
from xau_edge.market_data.broker_clock import BrokerClock

FetchRange = Callable[[datetime, datetime], pl.DataFrame]


def _month_start(moment: datetime) -> datetime:
    return datetime(moment.year, moment.month, 1, tzinfo=UTC)


def fetch_back(fetch: FetchRange, *, end: datetime, empty_run_stop: int = 6) -> pl.DataFrame:
    """Bars in ``[earliest available, end)`` by calendar-month windows, newest window first.

    Stops after ``empty_run_stop`` consecutive empty months. Returns an empty frame if the very
    first windows are empty. The result is sorted ascending with unique timestamps.
    """
    parts: list[pl.DataFrame] = []
    window_end = end
    empty_run = 0
    while empty_run < empty_run_stop:
        start = _month_start(window_end - timedelta(microseconds=1))
        frame = fetch(start, window_end)
        if frame.height:
            parts.append(frame)
            empty_run = 0
        else:
            empty_run += 1
        window_end = start
    if not parts:
        return empty_bars()
    return pl.concat(parts).unique(subset="timestamp").sort("timestamp")


def daily_from_h1(h1: pl.DataFrame, clock: BrokerClock, *, min_bars: int = 12) -> pl.DataFrame:
    """Daily OHLC from H1 bars grouped by the broker's server calendar day.

    ``timestamp`` is the UTC open of the first H1 bar of the day; ``n_bars`` counts the H1 bars.
    Days with fewer than ``min_bars`` bars (holidays, partial weeks) are dropped, never padded.
    The still-incomplete last day must not be passed in: callers cut H1 at a closed day.
    """
    server_day = clock.utc_to_server(pl.col("timestamp")).dt.date().alias("server_day")
    daily = (
        h1.sort("timestamp")
        .with_columns(server_day)
        .group_by("server_day", maintain_order=True)
        .agg(
            pl.col("timestamp").first(),
            pl.col("open").first(),
            pl.col("high").max(),
            pl.col("low").min(),
            pl.col("close").last(),
            pl.col("tick_volume").sum(),
            pl.col("spread").median().alias("spread_median"),
            pl.len().alias("n_bars"),
        )
        .filter(pl.col("n_bars") >= min_bars)
        .drop("server_day")
    )
    return daily
