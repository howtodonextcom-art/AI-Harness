from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import polars as pl

from tests.conftest import write_live, write_series
from xau_edge_v2.data.bar_store import BarStore
from xau_edge_v2.data.broker_profile import default_calendar
from xau_edge_v2.data.live_feed import LiveFeed
from xau_edge_v2.data.store_status import build_store_status, stale_after_seconds
from xau_edge_v2.data.tick_store import TickStore
from xau_edge_v2.domain.contract import Timeframe

WEDNESDAY_NOON_NY = datetime(2026, 10, 14, 16, 0, tzinfo=UTC)  # 12:00 NY (EDT): market open
SATURDAY = datetime(2026, 10, 17, 14, 0, tzinfo=UTC)


def test_quote_fresh_stale_and_closed(tmp_path: Path) -> None:
    cal = default_calendar()
    write_live(tmp_path, at=WEDNESDAY_NOON_NY, quote_age_s=2.0, file_age_s=1.0)
    feed = LiveFeed(tmp_path, cache_seconds=0.0)
    fresh = feed.quote(cal, now=WEDNESDAY_NOON_NY)
    assert fresh.state == "FRESH" and fresh.available and fresh.bid == 4165.43
    assert fresh.spread_points == 35.0 and fresh.age_seconds == 2.0
    # two minutes later with no new write: market open, quote older than 30 s -> STALE
    assert feed.quote(cal, now=WEDNESDAY_NOON_NY + timedelta(minutes=2)).state == "STALE"
    # the market is closed on Saturday: the last known quote is shown as MARKET_CLOSED, not STALE
    closed = feed.quote(cal, now=SATURDAY)
    assert closed.state == "MARKET_CLOSED" and closed.available and closed.bid == 4165.43


def test_missing_or_corrupt_live_file_is_unavailable_not_an_error(tmp_path: Path) -> None:
    cal = default_calendar()
    feed = LiveFeed(tmp_path, cache_seconds=0.0)
    assert feed.quote(cal).state == "UNAVAILABLE" and feed.symbol_info() is None
    (tmp_path / "live.json").write_text("{ half written", encoding="utf-8")
    assert feed.quote(cal).state == "UNAVAILABLE"


def test_symbol_spec_mapping_matches_v1_contract(tmp_path: Path) -> None:
    write_live(tmp_path, trade_tick_size=0.01, trade_tick_value=1.0, volume_step=0.01)
    info = LiveFeed(tmp_path, cache_seconds=0.0).symbol_info()
    assert info is not None and info.source == "BROKER_LIVE"
    assert (info.point, info.tick_size, info.tick_value) == (0.01, 0.01, 1.0)
    assert (info.contract_size, info.volume_min, info.volume_step, info.volume_max) == (
        100.0,
        0.01,
        0.01,
        100.0,
    )
    assert (info.stops_level_points, info.freeze_level_points, info.digits) == (0, 0, 2)


def test_symbol_spec_missing_field_is_none(tmp_path: Path) -> None:
    write_live(tmp_path)
    raw = (
        (tmp_path / "live.json")
        .read_text(encoding="utf-8")
        .replace('"trade_tick_value": 1.0, ', "")
    )
    (tmp_path / "live.json").write_text(raw, encoding="utf-8")
    assert LiveFeed(tmp_path, cache_seconds=0.0).symbol_info() is None


def test_tick_store_half_open_and_ordered(tmp_path: Path) -> None:
    folder = tmp_path / "XAUUSD" / "ticks" / "2026"
    folder.mkdir(parents=True)
    base = datetime(2026, 10, 12, 0, 0, tzinfo=UTC)
    stamps = [base + timedelta(milliseconds=500 * i) for i in range(20)]
    frame = pl.DataFrame(
        {
            "timestamp_msc": [int(t.timestamp() * 1000) for t in stamps],
            "timestamp": stamps,
            "bid": [1.0 + i for i in range(20)],
            "ask": [1.1 + i for i in range(20)],
            "last": [0.0] * 20,
            "volume": [0] * 20,
            "flags": [0] * 20,
        }
    ).with_columns(pl.col("timestamp").dt.replace_time_zone("UTC").dt.cast_time_unit("ms"))
    frame.write_parquet(folder / "2026-10-12.parquet")
    store = TickStore(tmp_path)
    got = store.load(stamps[2], stamps[7], limit=100)
    assert got["timestamp"].to_list() == stamps[2:7]  # [start, end)
    assert store.load(stamps[0], stamps[19] + timedelta(seconds=1), limit=3).height == 3
    assert store.first_day() == store.last_day() == "2026-10-12"
    assert TickStore(tmp_path / "none").load(stamps[0], stamps[1]).height == 0


def _bars(tmp_path: Path, last_open: datetime, tf: Timeframe = Timeframe.M1) -> BarStore:
    write_series(tmp_path, tf, last_open - timedelta(minutes=10), 11, step_minutes=1)
    return BarStore(tmp_path, cache_seconds=0.0)


def test_freshness_open_market(tmp_path: Path) -> None:
    now = WEDNESDAY_NOON_NY
    store = _bars(tmp_path, now - timedelta(minutes=2))
    row = next(
        t
        for t in build_store_status(store, default_calendar(), now).timeframes
        if t.timeframe is Timeframe.M1
    )
    assert row.state == "FRESH" and row.age_seconds == 60.0 and row.open_age_seconds == 60.0


def test_freshness_stale_only_when_the_market_was_open(tmp_path: Path) -> None:
    cal = default_calendar()
    now = WEDNESDAY_NOON_NY
    stale = _bars(tmp_path / "a", now - timedelta(hours=2))
    row = next(
        t for t in build_store_status(stale, cal, now).timeframes if t.timeframe is Timeframe.M1
    )
    assert row.state == "STALE" and (row.open_age_seconds or 0) > stale_after_seconds(Timeframe.M1)
    # weekend: a bar from Friday's last minutes is NOT stale on Saturday
    friday = datetime(2026, 10, 16, 20, 49, tzinfo=UTC)  # 16:49 NY: the last M1 bar of the week
    weekend = _bars(tmp_path / "b", friday)
    sat = next(
        t
        for t in build_store_status(weekend, cal, SATURDAY).timeframes
        if t.timeframe is Timeframe.M1
    )
    assert sat.state == "MARKET_CLOSED"
    # ...but a store that stopped on Tuesday is stale by Saturday even though the market is closed
    tuesday = _bars(tmp_path / "c", datetime(2026, 10, 13, 12, 0, tzinfo=UTC))
    old = next(
        t
        for t in build_store_status(tuesday, cal, SATURDAY).timeframes
        if t.timeframe is Timeframe.M1
    )
    assert old.state == "STALE"


def test_freshness_unknown_without_data(tmp_path: Path) -> None:
    status = build_store_status(
        BarStore(tmp_path / "nothing"), default_calendar(), WEDNESDAY_NOON_NY
    )
    assert not status.reachable and all(t.state == "UNKNOWN" for t in status.timeframes)
