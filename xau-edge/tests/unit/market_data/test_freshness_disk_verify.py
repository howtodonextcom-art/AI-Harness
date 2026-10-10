"""Calendar-aware freshness, disk health, event segmentation, locking and ledger verification."""

from __future__ import annotations

import shutil
import threading
from collections import namedtuple
from datetime import UTC, datetime, timedelta
from pathlib import Path

import polars as pl
import pytest

from tests.unit.market_data.test_collector_ledger import FakeClient, bars, make_feed
from tests.unit.market_data.test_tick_ledger import ticks, window
from xau_edge.domain.market import MarketStatus
from xau_edge.domain.timeframe import Timeframe
from xau_edge.market_data import disk
from xau_edge.market_data.calendars import ftmo_calendar
from xau_edge.market_data.disk import DiskThresholds, disk_report
from xau_edge.market_data.event_log import append_event, read_events
from xau_edge.market_data.freshness import (
    bar_freshness,
    consistency_warnings,
    missed_closed_bars,
)
from xau_edge.market_data.ledger import BarLedger
from xau_edge.market_data.locking import LockTimeoutError, file_lock
from xau_edge.market_data.tick_ledger import TickLedger
from xau_edge.market_data.verification import verify_bars, verify_ticks

CAL = ftmo_calendar()
WED_NOON = datetime(2026, 3, 11, 12, 0, 30, tzinfo=UTC)


def test_h4_last_closed_one_hour_ago_is_fresh_but_m1_five_minutes_late_is_stale() -> None:
    h4_open = datetime(2026, 3, 11, 7, tzinfo=UTC)  # closed 11:00, "now" is 12:00:30
    assert missed_closed_bars(h4_open, Timeframe.H4, WED_NOON, CAL) == 0
    assert bar_freshness(0, Timeframe.H4) == "FRESH"
    m1_open = WED_NOON - timedelta(minutes=10)
    missed = missed_closed_bars(m1_open, Timeframe.M1, WED_NOON, CAL)
    assert missed is not None and missed >= 8
    assert bar_freshness(missed, Timeframe.M1) == "STALE"


def test_nothing_is_missed_across_the_weekend_or_daily_break() -> None:
    friday_last = datetime(2026, 3, 13, 20, 49, tzinfo=UTC)  # 16:49 NY (EDT after Mar 8)
    sunday_after_reopen = datetime(2026, 3, 15, 22, 5, 30, tzinfo=UTC)
    assert missed_closed_bars(friday_last, Timeframe.M1, sunday_after_reopen, CAL) == 0
    break_start = datetime(2026, 3, 11, 20, 49, tzinfo=UTC)
    assert (
        missed_closed_bars(break_start, Timeframe.M1, break_start + timedelta(minutes=70), CAL) == 0
    )


def test_unknown_when_nothing_stored() -> None:
    assert missed_closed_bars(None, Timeframe.M5, WED_NOON, CAL) is None
    assert bar_freshness(None, Timeframe.M5) == "UNKNOWN"


def test_consistency_warnings_flag_old_quote_and_out_of_range_but_not_normal() -> None:
    feed = make_feed(FakeClient())
    quote = feed.quote(feed.discover_symbol("XAUUSD"), MarketStatus.OPEN)
    open_time = (quote.timestamp - timedelta(minutes=1)).isoformat() if quote.timestamp else ""
    good = {"M1": {"timestamp": open_time, "low": 1999.0, "high": 2001.0}}
    assert consistency_warnings(quote, good) == []
    bad = {
        "M1": {
            "timestamp": (WED_NOON + timedelta(hours=1)).isoformat(),
            "low": 100.0,
            "high": 101.0,
        }
    }
    messages = consistency_warnings(quote, bad)
    assert len(messages) == 2
    assert consistency_warnings(None, good) == []


def test_disk_report_levels_and_growth(tmp_path: Path) -> None:
    ledger = TickLedger(tmp_path)
    start = datetime(2026, 3, 11, 10, tzinfo=UTC)
    ledger.append("XAUUSD", ticks(start, 500), window(start, 10), now=WED_NOON)
    report = disk_report(tmp_path)
    assert report["level"] in {"GOOD", "WARN", "CRITICAL"}
    assert report["tick_days_stored"] == 1
    assert report["tick_mb_per_stored_day"] is not None
    strict = disk_report(
        tmp_path, thresholds=DiskThresholds(warn_free_gb=1e9, critical_free_gb=1e8)
    )
    assert strict["level"] == "CRITICAL"


def test_event_log_segments_without_losing_history(tmp_path: Path) -> None:
    path = tmp_path / "events.jsonl"
    for i in range(30):
        append_event(path, {"i": i}, max_bytes=100)
    assert len(list(tmp_path.glob("events-*.jsonl"))) >= 2
    assert [e["i"] for e in read_events(path)] == list(range(30))
    with path.open("a", encoding="utf-8") as handle:
        handle.write("{torn\n")
    assert len(read_events(path)) == 30


def test_file_lock_serialises_writers_and_clears_stale_locks(tmp_path: Path) -> None:
    lock = tmp_path / "x.lock"
    counter = {"n": 0, "max": 0, "inside": 0}

    def worker() -> None:
        for _ in range(5):
            with file_lock(lock, poll=0.001):
                counter["inside"] += 1
                counter["max"] = max(counter["max"], counter["inside"])
                counter["n"] += 1
                counter["inside"] -= 1

    threads = [threading.Thread(target=worker) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert counter["n"] == 20
    assert counter["max"] == 1
    assert not lock.exists()
    lock.write_text("", encoding="utf-8")
    with file_lock(lock, stale_seconds=-1):  # a crashed writer's lock is removed
        pass
    lock.write_text("", encoding="utf-8")
    with pytest.raises(LockTimeoutError), file_lock(lock, timeout=0.05, poll=0.01):
        pass


def test_verify_bars_clean_and_detects_corruption_and_history_change(tmp_path: Path) -> None:
    ledger = BarLedger(tmp_path)
    start = datetime(2026, 1, 5, 10, tzinfo=UTC)
    ledger.append_closed("XAUUSD", Timeframe.M5, bars(start, 40, 5), now=WED_NOON)
    first = verify_bars(ledger, "XAUUSD", CAL)
    assert first["ok"] and first["timeframes"]["M5"]["rows"] == 40
    saved = ledger.manifest("XAUUSD")
    later = datetime(2026, 3, 9, 10, tzinfo=UTC)
    ledger.append_closed("XAUUSD", Timeframe.M5, bars(later, 10, 5), now=WED_NOON)
    assert verify_bars(ledger, "XAUUSD", CAL, saved_manifest=saved)["ok"]  # growth is allowed
    month_file = tmp_path / "XAUUSD" / "M5" / "2026-01.parquet"
    frame = pl.read_parquet(month_file).with_columns(open=pl.col("open") + 1.0)
    frame.write_parquet(month_file)
    broken = verify_bars(ledger, "XAUUSD", CAL, saved_manifest=saved)
    assert not broken["ok"]
    assert any("historical files changed" in p for p in broken["timeframes"]["M5"]["problems"])
    month_file.write_bytes(b"not parquet")
    unreadable = verify_bars(ledger, "XAUUSD", CAL)
    assert not unreadable["ok"]


def test_verify_ticks_detects_crossed_quotes_and_changed_history(tmp_path: Path) -> None:
    ledger = TickLedger(tmp_path)
    day1 = datetime(2026, 3, 9, 10, tzinfo=UTC)
    day2 = datetime(2026, 3, 11, 10, tzinfo=UTC)
    ledger.append("XAUUSD", ticks(day1, 50), window(day1, 10), now=WED_NOON)
    ledger.append("XAUUSD", ticks(day2, 50), window(day2, 10), now=WED_NOON)
    assert verify_ticks(ledger, "XAUUSD")["ok"]
    saved = ledger.manifest("XAUUSD")
    crossed = ticks(day1 + timedelta(minutes=20), 2).with_columns(ask=pl.col("bid") - 1.0)
    ledger.append("XAUUSD", crossed, window(day1 + timedelta(minutes=20), 5), now=WED_NOON)
    report = verify_ticks(ledger, "XAUUSD", saved_manifest=saved)
    assert not report["ok"]
    assert report["crossed_ticks"] == 2
    assert any("historical days changed" in p for p in report["problems"])


def test_drives_report_flags_a_nearly_full_drive_that_does_not_hold_the_data(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    usage = namedtuple("usage", "total used free")
    anchor = tmp_path.resolve().anchor
    monkeypatch.setattr(disk, "_drive_roots", lambda: [Path(anchor), Path("Q:/")])
    monkeypatch.setattr(
        shutil,
        "disk_usage",
        lambda p: (
            usage(100e9, 87e9, 13e9)
            if str(p).upper().startswith("Q")
            else usage(200e9, 100e9, 100e9)
        ),
    )
    report = disk.drives_report(tmp_path)
    by_level = {d["drive"]: d for d in report}
    low = next(d for d in report if str(d["drive"]).upper().startswith("Q"))
    assert low["level"] == "WARN" and low["free_gb"] == 13.0 and low["holds_market_data"] is False
    holder = next(d for d in report if d["holds_market_data"])
    assert holder["level"] == "GOOD"
    assert len(by_level) == 2
