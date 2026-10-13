"""Incremental refresh of the raw store from a bar source (read-only market data).

Fetches only what is missing (from a little before the newest stored bar up to the last CLOSED bar),
appends it to the immutable raw store as a new dataset (the catalog merges it, newest wins).
The still-forming bar is never stored. Raw data is never modified: a failed or empty fetch leaves
the store as it was.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta

from xau_edge.domain.bars import BarRequest
from xau_edge.domain.timeframe import Timeframe
from xau_edge.market_data.source import BarSource
from xau_edge.market_data.store import RawStore
from xau_edge.observability import log_event

_LOG = logging.getLogger(__name__)
OVERLAP_BARS = 3
"""Re-fetch a few bars before the newest stored one so a bar stored while forming is replaced."""


@dataclass(frozen=True)
class RefreshResult:
    """What a refresh did for one timeframe."""

    timeframe: Timeframe
    fetched_rows: int
    newest: datetime | None


def refresh_market_data(
    source: BarSource,
    store: RawStore,
    symbol: str,
    now: datetime,
    *,
    source_name: str,
    timeframes: tuple[Timeframe, ...] = (Timeframe.M5, Timeframe.M15, Timeframe.H1, Timeframe.H4),
    initial_lookback: timedelta = timedelta(days=14),
) -> list[RefreshResult]:
    """Fetch bars newer than the store holds for every timeframe and store them."""
    results: list[RefreshResult] = []
    for tf in timeframes:
        stored = store.datasets(symbol, tf)
        newest = max(d.end for d in stored) if stored else None
        start = newest - tf.delta * OVERLAP_BARS if newest is not None else now - initial_lookback
        bars = source.fetch_bars(BarRequest(symbol=symbol, timeframe=tf, start=start, end=now))
        bars = bars.filter(bars["timestamp"] + tf.delta <= now)  # closed bars only
        if bars.height:
            store.write(bars, symbol=symbol, timeframe=tf, source=source_name, fetched_at=now)
        latest = bars["timestamp"].max() if bars.height else newest
        log_event(_LOG, "refresh.done", timeframe=tf.value, rows=bars.height)
        results.append(
            RefreshResult(tf, bars.height, latest if isinstance(latest, datetime) else None)
        )
    return results
