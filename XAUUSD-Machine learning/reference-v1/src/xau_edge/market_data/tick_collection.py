"""Tick fetching into the tick ledger: whole-window or split, never silently truncated."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from xau_edge.market_data.mt5.feed import MAX_TICKS_PER_CALL, Mt5Feed
from xau_edge.market_data.tick_ledger import TickLedger

MIN_SPLIT = timedelta(seconds=2)


@dataclass
class FetchStats:
    windows: int = 0
    ticks_received: int = 0
    ticks_new: int = 0
    conflicts: int = 0
    unsplittable: list[str] = field(default_factory=list)


def fetch_window(
    feed: Mt5Feed,
    ledger: TickLedger,
    *,
    symbol: str,
    broker_symbol: str,
    start: datetime,
    end: datetime,
    stats: FetchStats,
    reason: str = "backfill",
) -> None:
    """Fetch ``[start, end)`` completely (halving on the per-call cap) and store it."""
    frame, truncated = feed.ticks_frame(broker_symbol, start, end, limit=MAX_TICKS_PER_CALL)
    if truncated:
        if end - start <= MIN_SPLIT:
            stats.unsplittable.append(start.isoformat())
            return
        mid = (start + (end - start) / 2).replace(microsecond=0)
        for lo, hi in ((start, mid), (mid, end)):
            fetch_window(
                feed, ledger, symbol=symbol, broker_symbol=broker_symbol,
                start=lo, end=hi, stats=stats, reason=reason,
            )  # fmt: skip
        return
    result = ledger.append(symbol, frame, (start, end), now=datetime.now(UTC), reason=reason)
    stats.windows += 1
    stats.ticks_received += result.received
    stats.ticks_new += result.new
    stats.conflicts += result.conflicts


def ingest_recent(
    feed: Mt5Feed,
    ledger: TickLedger,
    *,
    symbol: str,
    broker_symbol: str,
    now: datetime,
    lag: timedelta = timedelta(seconds=3),
    max_catch_up: timedelta = timedelta(hours=24),
    chunk: timedelta = timedelta(hours=1),
) -> FetchStats:
    """Live ingestion: tick the ledger up to ``now - lag`` (older gaps are left to the backfill)."""
    stats = FetchStats()
    end = (now - lag).replace(microsecond=0)
    covered = ledger.coverage(symbol)
    start = max(b for _, b in covered) if covered else end - timedelta(seconds=60)
    start = max(start, end - max_catch_up)
    if end - start < timedelta(seconds=1):
        return stats
    cursor = start
    while cursor < end:
        hi = min(end, cursor + chunk)
        fetch_window(
            feed, ledger, symbol=symbol, broker_symbol=broker_symbol,
            start=cursor, end=hi, stats=stats, reason="live",
        )  # fmt: skip
        cursor = hi
    return stats
