"""Tick ledger: append-only, idempotent, coverage, conflicts, archive, and the feed's tick frame."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import numpy as np
import polars as pl
import pytest

from tests.unit.market_data.test_collector_ledger import FakeClient, make_feed
from xau_edge.domain.market import conform_ticks
from xau_edge.market_data.tick_ledger import TickLedger, TickLedgerError

NOW = datetime(2026, 3, 12, 12, 0, tzinfo=UTC)


def ticks(start: datetime, n: int, step_ms: int = 500, bid: float = 2000.0) -> pl.DataFrame:
    base = int(start.timestamp() * 1000)
    msc = [base + i * step_ms for i in range(n)]
    return conform_ticks(
        pl.DataFrame(
            {
                "timestamp_msc": msc,
                "timestamp": pl.Series(msc).cast(pl.Datetime("ms")).dt.replace_time_zone("UTC"),
                "bid": [bid + i * 0.01 for i in range(n)],
                "ask": [bid + 0.3 + i * 0.01 for i in range(n)],
                "last": [0.0] * n,
                "volume": [0] * n,
                "flags": [134] * n,
            }
        )
    )


def window(start: datetime, minutes: int) -> tuple[datetime, datetime]:
    return start, start + timedelta(minutes=minutes)


def test_append_is_idempotent_and_records_coverage(tmp_path: Path) -> None:
    ledger = TickLedger(tmp_path)
    start = datetime(2026, 3, 11, 10, tzinfo=UTC)
    frame = ticks(start, 100)
    first = ledger.append("XAUUSD", frame, window(start, 10), now=NOW)
    again = ledger.append("XAUUSD", frame, window(start, 10), now=NOW)
    assert (first.new, again.new, again.conflicts) == (100, 0, 0)
    assert ledger.load("XAUUSD", start, start + timedelta(hours=1)).height == 100
    assert ledger.coverage("XAUUSD") == [window(start, 10)]
    assert ledger.uncovered("XAUUSD", start, start + timedelta(minutes=30)) == [
        (start + timedelta(minutes=10), start + timedelta(minutes=30))
    ]


def test_adjacent_windows_merge_and_empty_window_still_counts_as_covered(tmp_path: Path) -> None:
    ledger = TickLedger(tmp_path)
    start = datetime(2026, 3, 11, 10, tzinfo=UTC)
    ledger.append("XAUUSD", ticks(start, 10), window(start, 10), now=NOW)
    ledger.append("XAUUSD", pl.DataFrame(), window(start + timedelta(minutes=10), 10), now=NOW)
    assert ledger.coverage("XAUUSD") == [window(start, 20)]


def test_stored_ticks_are_authoritative_and_a_different_answer_is_an_event(tmp_path: Path) -> None:
    ledger = TickLedger(tmp_path)
    start = datetime(2026, 3, 11, 10, tzinfo=UTC)
    ledger.append("XAUUSD", ticks(start, 20), window(start, 10), now=NOW)
    result = ledger.append("XAUUSD", ticks(start, 20, bid=2100.0), window(start, 10), now=NOW)
    assert result.new == 0 and result.conflicts == 20
    stored = ledger.load("XAUUSD", start, start + timedelta(hours=1))
    assert stored["bid"][0] == pytest.approx(2000.0)
    assert [e["kind"] for e in ledger.events("XAUUSD")] == ["TICKS_CHANGED"]


def test_partitions_by_utc_day_and_bounds_load(tmp_path: Path) -> None:
    ledger = TickLedger(tmp_path)
    start = datetime(2026, 3, 11, 23, 55, tzinfo=UTC)
    ledger.append("XAUUSD", ticks(start, 1200, step_ms=1000), window(start, 20), now=NOW)
    assert ledger.days("XAUUSD") == ["2026-03-11", "2026-03-12"]
    assert ledger.load("XAUUSD", start, start + timedelta(minutes=30), limit=50).height == 50
    manifest = ledger.manifest("XAUUSD")
    assert manifest["rows"] == 1200 and len(manifest["dataset_id"]) == 16


def test_same_millisecond_distinct_ticks_are_kept_but_exact_duplicates_dropped(
    tmp_path: Path,
) -> None:
    ledger = TickLedger(tmp_path)
    start = datetime(2026, 3, 11, 10, tzinfo=UTC)
    frame = ticks(start, 3)
    clash = frame.head(1).with_columns(bid=pl.lit(1.0))
    dup = frame.head(1)
    result = ledger.append("XAUUSD", pl.concat([frame, clash, dup]), window(start, 5), now=NOW)
    assert result.new == 4
    assert ledger.load("XAUUSD", start, start + timedelta(hours=1)).height == 4


def test_rejects_future_window_out_of_window_ticks_and_unsafe_symbol(tmp_path: Path) -> None:
    ledger = TickLedger(tmp_path)
    start = datetime(2026, 3, 11, 10, tzinfo=UTC)
    with pytest.raises(TickLedgerError, match="not ended"):
        ledger.append("XAUUSD", pl.DataFrame(), window(NOW, 10), now=NOW)
    with pytest.raises(TickLedgerError, match="outside"):
        ledger.append("XAUUSD", ticks(start, 10), window(start + timedelta(minutes=1), 5), now=NOW)
    with pytest.raises(TickLedgerError, match="unsafe"):
        ledger.coverage("../x")


def test_archive_moves_old_days_with_hash_check_and_keeps_coverage(tmp_path: Path) -> None:
    ledger = TickLedger(tmp_path / "live")
    start = datetime(2026, 3, 9, 10, tzinfo=UTC)
    ledger.append("XAUUSD", ticks(start, 10), window(start, 10), now=NOW)
    later = datetime(2026, 3, 11, 10, tzinfo=UTC)
    ledger.append("XAUUSD", ticks(later, 10), window(later, 10), now=NOW)
    moved = ledger.archive_before("XAUUSD", "2026-03-10", tmp_path / "archive")
    assert moved == ["2026-03-09"] and ledger.days("XAUUSD") == ["2026-03-11"]
    assert (tmp_path / "archive" / "XAUUSD" / "ticks" / "2026" / "2026-03-09.parquet").exists()
    assert len(ledger.coverage("XAUUSD")) == 2  # the gap stays visible


def test_feed_tick_frame_filters_exactly_and_flags_truncation() -> None:
    client = FakeClient()
    base = int(datetime(2026, 3, 11, 10, tzinfo=UTC).timestamp())
    dtype = [
        ("time", "i8"),
        ("bid", "f8"),
        ("ask", "f8"),
        ("last", "f8"),
        ("volume", "i8"),
        ("time_msc", "i8"),
        ("flags", "i4"),
        ("volume_real", "f8"),
    ]
    rows = [
        (base + i // 2, 2000.0, 2000.3, 0.0, 0, (base + i // 2) * 1000 + (i % 2) * 500, 134, 0.0)
        for i in range(-4, 24)
    ]

    def copy_ticks_range(symbol: str, start: Any, end: Any, flags: int) -> Any:
        return np.array(rows, dtype=dtype)

    client.copy_ticks_range = copy_ticks_range  # type: ignore[attr-defined]
    feed = make_feed(client)
    start = datetime(2026, 3, 11, 10, tzinfo=UTC)
    frame, truncated = feed.ticks_frame("XAUUSD", start, start + timedelta(seconds=10))
    assert not truncated
    low, high = frame["timestamp"].min(), frame["timestamp"].max()
    assert isinstance(low, datetime)
    assert isinstance(high, datetime)
    assert low >= start
    assert high < start + timedelta(seconds=10)
    assert frame.schema["timestamp"] == pl.Datetime("ms", "UTC")
    cut, flagged = feed.ticks_frame("XAUUSD", start, start + timedelta(seconds=10), limit=5)
    assert flagged and cut.height <= 5
    assert cast(Any, SimpleNamespace(x=1)).x == 1
