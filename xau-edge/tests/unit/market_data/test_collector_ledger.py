"""Bar ledger, collector, health and session tests on a fake MT5 client (no live terminal)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import numpy as np
import polars as pl
import pytest

from xau_edge.domain.market import FeedHealth, MarketStatus
from xau_edge.domain.timeframe import Timeframe
from xau_edge.market_data.broker_clock import BrokerClock
from xau_edge.market_data.collector import (
    MarketCollector,
    evaluate_health,
    read_status_file,
)
from xau_edge.market_data.ledger import BarLedger, LedgerError
from xau_edge.market_data.mt5.feed import Mt5Feed, SymbolNotFoundError
from xau_edge.market_data.session import market_status
from xau_edge.market_data.validators.market_calendar import MarketCalendar

DTYPE = [
    ("time", "i8"), ("open", "f8"), ("high", "f8"), ("low", "f8"), ("close", "f8"),
    ("tick_volume", "i8"), ("spread", "i4"), ("real_volume", "i8"),
]  # fmt: skip
MINUTES = {"M1": 1, "M5": 5, "M15": 15, "M30": 30, "H1": 60, "H4": 240}
# Wednesday: the market is open all day, so no weekend/rollover effects in these tests.
NOW = datetime(2026, 3, 11, 12, 0, 30, tzinfo=UTC)


def make_rates(start: datetime, minutes: int, count: int, *, bump: float = 0.0) -> Any:
    rows = []
    for i in range(count):
        t = start + timedelta(minutes=minutes * i)
        slot = int(t.timestamp() // 60)
        base = 2000.0 + (slot % 500) * 0.1 + bump
        rows.append(
            (int(t.timestamp()), base, base + 1, base - 1, base + 0.5, 100 + slot % 50, 20, 0)
        )
    return np.array(rows, dtype=DTYPE)


class FakeClient:
    ACCOUNT_TRADE_MODE_DEMO = 0
    COPY_TICKS_ALL = 0
    TIMEFRAME_M1, TIMEFRAME_M5, TIMEFRAME_M15 = 1, 5, 15
    TIMEFRAME_M30, TIMEFRAME_H1, TIMEFRAME_H4 = 30, 16385, 16388

    def __init__(self, now: datetime = NOW, *, trade_mode: int = 0) -> None:
        self.now = now
        self.trade_mode = trade_mode
        self.bump = 0.0
        self.connected = True
        self.tick_age = 1.0
        self.symbols = ["XAUUSD", "EURUSD"]

    def account_info(self) -> Any:
        return SimpleNamespace(trade_mode=self.trade_mode, server="FTMO-Demo")

    def terminal_info(self) -> Any:
        return SimpleNamespace(
            build=6241,
            connected=self.connected,
            trade_allowed=False,
            maxbars=100000,
            company="FTMO",
        )

    def version(self) -> Any:
        return (500, 6241, "01 Jan 2026")

    def symbols_get(self) -> Any:
        return [SimpleNamespace(name=n) for n in self.symbols]

    def symbol_select(self, name: str, enable: bool) -> bool:
        return True

    def symbol_info(self, name: str) -> Any:
        return SimpleNamespace(point=0.01)

    def symbol_info_tick(self, name: str) -> Any:
        stamp = self.now - timedelta(seconds=self.tick_age)
        return SimpleNamespace(
            time=int(stamp.timestamp()), time_msc=int(stamp.timestamp() * 1000),
            bid=2000.0, ask=2000.2, last=0.0,
        )  # fmt: skip

    def last_error(self) -> tuple[int, str]:
        return (1, "ok")

    def copy_rates_from_pos(self, symbol: str, tf: int, pos: int, count: int) -> Any:
        minutes = {1: 1, 5: 5, 15: 15, 30: 30, 16385: 60, 16388: 240}[tf]
        step = timedelta(minutes=minutes)
        epoch = datetime(2026, 1, 1, tzinfo=UTC)
        slots = int((self.now - epoch) / step)
        last_open = epoch + step * slots  # the forming bar
        start = last_open - step * (count - 1)
        return make_rates(start, minutes, count, bump=self.bump)


def make_feed(client: FakeClient) -> Mt5Feed:
    return Mt5Feed(cast(Any, client), BrokerClock(iana="UTC"), now=lambda: client.now)


def make_collector(tmp_path: Path, client: FakeClient) -> MarketCollector:
    feed = make_feed(client)
    return MarketCollector(
        feed, BarLedger(tmp_path), feed.discover_symbol("XAUUSD"), MarketCalendar(),
        status_path=tmp_path / "collector_status.json", now=lambda: client.now,
    )  # fmt: skip


def bars(start: datetime, count: int, minutes: int = 1, bump: float = 0.0) -> pl.DataFrame:
    return make_feed(FakeClient())._frame(make_rates(start, minutes, count, bump=bump))


# -- ledger -----------------------------------------------------------------------------------


def test_ledger_append_is_idempotent(tmp_path: Path) -> None:
    ledger = BarLedger(tmp_path)
    frame = bars(datetime(2026, 3, 9, 10, tzinfo=UTC), 30)
    first = ledger.append_closed("XAUUSD", Timeframe.M1, frame, now=NOW)
    second = ledger.append_closed("XAUUSD", Timeframe.M1, frame, now=NOW)
    assert (first.new, first.duplicates) == (30, 0)
    assert (second.new, second.duplicates, second.changed) == (0, 30, 0)
    assert ledger.load("XAUUSD", Timeframe.M1).height == 30


def test_ledger_never_overwrites_and_records_change(tmp_path: Path) -> None:
    ledger = BarLedger(tmp_path)
    start = datetime(2026, 3, 9, 10, tzinfo=UTC)
    ledger.append_closed("XAUUSD", Timeframe.M1, bars(start, 5), now=NOW)
    result = ledger.append_closed("XAUUSD", Timeframe.M1, bars(start, 5, bump=3.0), now=NOW)
    assert result.changed == 5
    assert ledger.load("XAUUSD", Timeframe.M1)["open"][0] == pytest.approx(
        bars(start, 1)["open"][0]
    )
    assert [e["kind"] for e in ledger.events("XAUUSD")] == ["BAR_CHANGED"]


def test_ledger_refuses_forming_bar(tmp_path: Path) -> None:
    ledger = BarLedger(tmp_path)
    forming = bars(NOW.replace(second=0), 1)
    with pytest.raises(LedgerError):
        ledger.append_closed("XAUUSD", Timeframe.M1, forming, now=NOW)


def test_ledger_rejects_unsafe_symbol_and_hashes_files(tmp_path: Path) -> None:
    ledger = BarLedger(tmp_path)
    with pytest.raises(LedgerError):
        ledger.latest("../x", Timeframe.M1)
    ledger.append_closed(
        "XAUUSD", Timeframe.M1, bars(datetime(2026, 3, 9, 10, tzinfo=UTC), 3), now=NOW
    )
    manifest = ledger.manifest("XAUUSD")
    assert manifest["timeframes"]["M1"]["rows"] == 3
    assert len(manifest["timeframes"]["M1"]["dataset_id"]) == 16


def test_ledger_splits_months_and_survives_torn_event_line(tmp_path: Path) -> None:
    ledger = BarLedger(tmp_path)
    frame = bars(datetime(2026, 2, 27, 0, tzinfo=UTC), 3, minutes=60 * 24)
    ledger.append_closed("XAUUSD", Timeframe.H4, frame, now=NOW)
    assert ledger.months("XAUUSD", Timeframe.H4) == ["2026-02", "2026-03"]
    ledger.log_event("XAUUSD", "X", {}, now=NOW)
    with (tmp_path / "XAUUSD" / "events.jsonl").open("a", encoding="utf-8") as h:
        h.write("{torn\n")
    assert len(ledger.events("XAUUSD")) == 1


# -- feed -------------------------------------------------------------------------------------


def test_feed_quote_fresh_and_stale() -> None:
    client = FakeClient()
    feed = make_feed(client)
    mapping = feed.discover_symbol("XAUUSD")
    fresh = feed.quote(mapping, MarketStatus.OPEN)
    assert fresh.spread_points == pytest.approx(20.0) and not fresh.stale
    client.tick_age = 120.0
    assert feed.quote(mapping, MarketStatus.OPEN).stale
    assert not feed.quote(mapping, MarketStatus.CLOSED).stale


def test_feed_symbol_missing_and_non_demo_fail_closed() -> None:
    client = FakeClient()
    client.symbols = ["EURUSD"]
    with pytest.raises(SymbolNotFoundError):
        make_feed(client).discover_symbol("XAUUSD")
    with pytest.raises(Exception, match="not a DEMO"):
        make_feed(FakeClient(trade_mode=2)).discover_symbol("XAUUSD")


def test_feed_latest_bars_excludes_forming_by_default() -> None:
    client = FakeClient()
    feed = make_feed(client)
    closed = feed.latest_bars("XAUUSD", Timeframe.M5, 10)
    everything = feed.latest_bars("XAUUSD", Timeframe.M5, 10, include_forming=True)
    assert everything.height == closed.height + 1
    newest = closed["timestamp"].max()
    assert isinstance(newest, datetime)
    assert newest + timedelta(minutes=5) <= NOW


# -- collector --------------------------------------------------------------------------------


def test_collector_stores_closed_bars_for_all_timeframes_and_is_idempotent(tmp_path: Path) -> None:
    client = FakeClient()
    collector = make_collector(tmp_path, client)
    collector.poll_bars()
    rows = {tf: collector.ledger.load("XAUUSD", tf).height for tf in collector.timeframes}
    assert all(n > 0 for n in rows.values())
    collector.poll_bars()
    assert {tf: collector.ledger.load("XAUUSD", tf).height for tf in collector.timeframes} == rows
    latest = collector.ledger.latest("XAUUSD", Timeframe.M1)
    assert latest is not None and latest + timedelta(minutes=1) <= NOW


def test_collector_picks_up_new_bar_after_time_passes(tmp_path: Path) -> None:
    client = FakeClient()
    collector = make_collector(tmp_path, client)
    collector.poll_bars()
    before = collector.ledger.load("XAUUSD", Timeframe.M1).height
    client.now += timedelta(minutes=3)
    collector.poll_bars()
    assert collector.ledger.load("XAUUSD", Timeframe.M1).height == before + 3


def test_reconcile_after_restart_fills_gap_and_flags_changes(tmp_path: Path) -> None:
    client = FakeClient()
    collector = make_collector(tmp_path, client)
    collector.poll_bars()
    client.now += timedelta(minutes=40)  # the collector was down for 40 minutes
    report = collector.reconcile(Timeframe.M1)
    assert report.missing_in_store >= 39 and report.changed == 0 and report.appended >= 39
    client.bump = 5.0  # the terminal now reports different prices for the same bars
    again = collector.reconcile(Timeframe.M1)
    assert again.changed > 0 and not again.clean
    assert "RECONCILE_DIFFERENCES" in {e["kind"] for e in collector.ledger.events("XAUUSD")}


def test_status_good_then_stale_when_quote_dies(tmp_path: Path) -> None:
    client = FakeClient()
    collector = make_collector(tmp_path, client)
    collector.run_once()
    status = collector.status()
    assert status.health == FeedHealth.GOOD.value and status.demo_account
    assert "login" not in str(status.__dict__).lower()
    client.tick_age = 600.0
    collector.poll_quote()
    assert collector.status().health == FeedHealth.STALE.value


def test_status_disconnected_and_status_file(tmp_path: Path) -> None:
    client = FakeClient()
    collector = make_collector(tmp_path, client)
    collector.run_once()
    client.connected = False
    assert collector.status().health == FeedHealth.DISCONNECTED.value
    stored = read_status_file(tmp_path / "collector_status.json", now=NOW)
    assert stored["collector_running"] is True
    old = read_status_file(tmp_path / "collector_status.json", now=NOW + timedelta(minutes=5))
    assert old["health"] == FeedHealth.STALE.value and old["collector_running"] is False
    missing = read_status_file(tmp_path / "nope.json")
    assert missing["health"] == FeedHealth.UNKNOWN.value


def test_run_loop_stops_and_never_calls_trading_functions(tmp_path: Path) -> None:
    client = FakeClient()
    collector = make_collector(tmp_path, client)
    ticks = iter(range(100))
    collector.run(lambda: next(ticks) >= 3, sleep=lambda _s: None, clock=lambda: 0.0)
    assert collector.ledger.latest("XAUUSD", Timeframe.M1) is not None
    with pytest.raises(AttributeError):
        collector.feed._client.order_send  # noqa: B018


# -- health and session -----------------------------------------------------------------------


def test_evaluate_health_closed_market_is_not_stale() -> None:
    health, _, stale = evaluate_health(
        connected=True, demo=True, market=MarketStatus.CLOSED, quote=None,
        freshness={"M1": "FRESH"}, recent_changes=0, store_ok=True,
    )  # fmt: skip
    assert health == FeedHealth.GOOD and stale == []


def test_evaluate_health_non_demo_is_unknown() -> None:
    health, reasons, _ = evaluate_health(
        connected=True, demo=False, market=MarketStatus.OPEN, quote=None,
        freshness={}, recent_changes=0, store_ok=True,
    )  # fmt: skip
    assert health == FeedHealth.UNKNOWN and "DEMO" in reasons[0]


def test_evaluate_health_changed_bars_degrade() -> None:
    health, _, _ = evaluate_health(
        connected=True, demo=True, market=MarketStatus.CLOSED, quote=None,
        freshness={}, recent_changes=2, store_ok=True,
    )  # fmt: skip
    assert health == FeedHealth.DEGRADED


def test_market_status_weekend_open_and_naive() -> None:
    cal = MarketCalendar()
    assert market_status(datetime(2026, 3, 11, 12, tzinfo=UTC), cal) == MarketStatus.OPEN
    assert market_status(datetime(2026, 3, 14, 12, tzinfo=UTC), cal) == MarketStatus.CLOSED
    naive = datetime(2026, 3, 11, 12)  # noqa: DTZ001
    assert market_status(naive, cal) == MarketStatus.UNKNOWN


def test_evaluate_health_stale_timeframe_only_matters_while_trading() -> None:
    stale = {"M1": "STALE", "H4": "FRESH"}
    closed, _, _ = evaluate_health(
        connected=True, demo=True, market=MarketStatus.CLOSED, quote=None,
        freshness=stale, recent_changes=0, store_ok=True,
    )  # fmt: skip
    assert closed == FeedHealth.STALE  # the freshness input already encodes missed open bars
    ok_quote = make_feed(FakeClient()).quote(
        make_feed(FakeClient()).discover_symbol("XAUUSD"), MarketStatus.OPEN
    )
    health, reasons, bad = evaluate_health(
        connected=True, demo=True, market=MarketStatus.OPEN, quote=ok_quote,
        freshness={"M1": "FRESH", "H4": "FRESH"}, recent_changes=0, store_ok=True,
        disk_level="CRITICAL", tick_lag_seconds=500.0,
    )  # fmt: skip
    assert health == FeedHealth.DEGRADED and bad == []
    assert any("disk" in r for r in reasons)
    assert any("tick ingestion" in r for r in reasons)


def test_ledger_tail_equals_load_tail_and_reads_few_months(tmp_path: Path) -> None:
    ledger = BarLedger(tmp_path)
    frame = bars(
        datetime(2025, 11, 1, tzinfo=UTC), 120, minutes=60 * 24
    )  # four months of D1-like bars
    ledger.append_closed("XAUUSD", Timeframe.H4, frame, now=NOW)
    assert ledger.tail("XAUUSD", Timeframe.H4, 10).equals(
        ledger.load("XAUUSD", Timeframe.H4).tail(10)
    )
    cut = datetime(2026, 1, 15, tzinfo=UTC)
    expected = ledger.load("XAUUSD", Timeframe.H4, end=cut).tail(7)
    assert ledger.tail("XAUUSD", Timeframe.H4, 7, end=cut).equals(expected)
    assert ledger.tail("XAUUSD", Timeframe.H4, 5, end=datetime(2020, 1, 1, tzinfo=UTC)).height == 0


def test_demo_guard_is_cached_briefly_but_never_caches_a_failure() -> None:
    client = FakeClient()
    calls = {"n": 0}
    original = client.account_info

    def counting() -> object:
        calls["n"] += 1
        return original()

    client.account_info = counting  # type: ignore[method-assign]
    feed = make_feed(client)
    for _ in range(10):
        feed.guard()
    assert calls["n"] == 1  # one account_info call, not ten
    client.now += timedelta(seconds=31)  # the cache expired: it asks again
    feed.guard()
    assert calls["n"] == 2
    client.trade_mode = 2  # the account turned into a live one
    client.now += timedelta(seconds=31)
    with pytest.raises(Exception, match="not a DEMO"):
        feed.guard()
    with pytest.raises(Exception, match="not a DEMO"):
        feed.guard()  # the refusal was not cached either


def test_just_closed_bar_waits_for_the_settle_delay(tmp_path: Path) -> None:
    client = FakeClient()
    client.now = datetime(2026, 3, 11, 12, 1, 5, tzinfo=UTC)  # the 12:00 bar closed only 5 s ago
    collector = make_collector(tmp_path, client)
    collector.poll_bars()
    latest = collector.ledger.latest("XAUUSD", Timeframe.M1)
    assert latest == datetime(2026, 3, 11, 11, 59, tzinfo=UTC)  # 12:00 is not stored yet
    client.now += timedelta(seconds=20)
    collector.poll_bars()
    assert collector.ledger.latest("XAUUSD", Timeframe.M1) == datetime(
        2026, 3, 11, 12, 0, tzinfo=UTC
    )


def test_a_changed_bar_is_reported_once_not_every_poll(tmp_path: Path) -> None:
    client = FakeClient()
    collector = make_collector(tmp_path, client)
    collector.poll_bars()
    client.bump = 3.0  # the terminal now reports different prices for bars already stored
    for _ in range(5):
        collector.poll_bars()
    events = [e for e in collector.ledger.events("XAUUSD") if e["kind"] == "BAR_CHANGED"]
    keys = [(e["timeframe"], t) for e in events for t in e["timestamps"]]
    assert keys
    assert len(keys) == len(set(keys))  # each differing bar appears in exactly one event


def test_audited_repair_replaces_only_flagged_bars_and_clears_the_health_count(
    tmp_path: Path,
) -> None:
    client = FakeClient()
    collector = make_collector(tmp_path, client)
    collector.run_once()
    client.bump = 4.0
    collector.poll_bars()
    assert collector.status().events_last_hour["changes"] > 0
    ledger = collector.ledger
    flagged_ts = [
        datetime.fromisoformat(t)
        for e in ledger.events("XAUUSD")
        if e["kind"] == "BAR_CHANGED" and e["timeframe"] == "M1"
        for t in e["timestamps"]
    ]
    live = make_feed(client).latest_bars("XAUUSD", Timeframe.M1, 100)
    live = live.filter(pl.col("timestamp").is_in(flagged_ts))
    done = ledger.replace_bars("XAUUSD", Timeframe.M1, live, now=client.now)
    assert len(done) == len(flagged_ts)
    assert done[0]["old"] != done[0]["new"]
    repaired = [e for e in ledger.events("XAUUSD") if e["kind"] == "BAR_REPAIRED"]
    assert repaired
    assert ledger.replace_bars("XAUUSD", Timeframe.M1, live, now=client.now) == []  # idempotent
    status = collector.status()
    m1_changes = [e for e in ledger.events("XAUUSD") if e["kind"] == "BAR_CHANGED"]
    assert m1_changes  # the history of the difference is kept
    assert status.events_last_hour["changes"] == sum(
        len([t for t in e["timestamps"] if e["timeframe"] != "M1"]) for e in m1_changes
    )
