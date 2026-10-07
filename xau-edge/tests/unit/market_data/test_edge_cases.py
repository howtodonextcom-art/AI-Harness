from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import polars as pl
import pytest

from tests.conftest import make_bars
from tests.unit.market_data.test_mt5_source import FakeMt5, request
from xau_edge.domain.bars import BarRequest
from xau_edge.domain.timeframe import Timeframe
from xau_edge.market_data.importers.file_source import FileBarSource
from xau_edge.market_data.mt5.source import Mt5BarSource, Mt5Settings
from xau_edge.market_data.source import BarSource
from xau_edge.market_data.validators import (
    IssueCode,
    MarketCalendar,
    ValidationConfig,
    validate_bars,
)

pytestmark = pytest.mark.unit

WIDE = BarRequest(
    symbol="XAUUSD",
    timeframe=Timeframe.M15,
    start=datetime(2025, 1, 1, tzinfo=UTC),
    end=datetime(2026, 1, 1, tzinfo=UTC),
)


def test_both_adapters_satisfy_the_bar_source_protocol(tmp_path: Path) -> None:
    file_src = FileBarSource(tmp_path / "x.csv", symbol="XAUUSD", timeframe=Timeframe.M15)
    mt5_src = Mt5BarSource(FakeMt5(None), Mt5Settings(broker_timezone="UTC"))
    assert isinstance(file_src, BarSource)
    assert isinstance(mt5_src, BarSource)


def test_daily_break_is_treated_as_closed() -> None:
    cal = MarketCalendar(
        timezone="UTC", daily_break_start_minute=21 * 60, daily_break_end_minute=22 * 60
    )
    cfg = ValidationConfig(calendar=cal)
    inside = datetime(2025, 3, 4, 21, 15, tzinfo=UTC)  # Tuesday, inside the break
    report = validate_bars(make_bars(1, start=inside), Timeframe.M15, config=cfg)
    assert IssueCode.WEEKEND_BARS in {i.code for i in report.issues}
    outside = datetime(2025, 3, 4, 20, 45, tzinfo=UTC)
    clean = validate_bars(make_bars(1, start=outside), Timeframe.M15, config=cfg)
    assert IssueCode.WEEKEND_BARS not in {i.code for i in clean.issues}


def test_daily_break_wrapping_midnight() -> None:
    cal = MarketCalendar(
        timezone="UTC", daily_break_start_minute=23 * 60 + 30, daily_break_end_minute=30
    )
    cfg = ValidationConfig(calendar=cal)
    at_0010 = datetime(2025, 3, 4, 0, 15, tzinfo=UTC)
    report = validate_bars(make_bars(1, start=at_0010), Timeframe.M15, config=cfg)
    assert IssueCode.WEEKEND_BARS in {i.code for i in report.issues}


def test_epoch_seconds_timestamps_are_read(tmp_path: Path) -> None:
    path = tmp_path / "bars.csv"
    epoch = int(datetime(2025, 3, 3, 0, 0, tzinfo=UTC).timestamp())
    path.write_text(
        f"time,open,high,low,close,tick_volume,spread\n{epoch},2000.0,2001.0,1999.0,2000.5,10,20\n",
        encoding="utf-8",
    )
    out = FileBarSource(path, symbol="XAUUSD", timeframe=Timeframe.M15).fetch_bars(WIDE)
    assert out["timestamp"][0] == datetime(2025, 3, 3, 0, 0, tzinfo=UTC)


def test_naive_parquet_timestamps_use_source_timezone(tmp_path: Path) -> None:
    df = make_bars(3).with_columns(pl.col("timestamp").dt.replace_time_zone(None))
    path = tmp_path / "naive.parquet"
    df.write_parquet(path)
    src = FileBarSource(
        path, symbol="XAUUSD", timeframe=Timeframe.M15, source_timezone="Europe/Athens"
    )
    out = src.fetch_bars(WIDE)
    assert out["timestamp"][0] == datetime(2025, 3, 2, 22, 0, tzinfo=UTC)


def test_non_utc_aware_parquet_timestamps_are_converted(tmp_path: Path) -> None:
    df = make_bars(3).with_columns(pl.col("timestamp").dt.convert_time_zone("Asia/Tokyo"))
    path = tmp_path / "tokyo.parquet"
    df.write_parquet(path)
    out = FileBarSource(path, symbol="XAUUSD", timeframe=Timeframe.M15).fetch_bars(WIDE)
    assert out["timestamp"].dtype == pl.Datetime("us", "UTC")
    assert out["timestamp"][0] == datetime(2025, 3, 3, 0, 0, tzinfo=UTC)


def test_unparseable_timestamps_raise(tmp_path: Path) -> None:
    path = tmp_path / "bad.csv"
    path.write_text(
        "timestamp,open,high,low,close,tick_volume,spread\nyesterday,1,1,1,1,1,1\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="Cannot parse timestamps"):
        FileBarSource(path, symbol="XAUUSD", timeframe=Timeframe.M15).fetch_bars(WIDE)


def test_offset_timestamps_with_z_suffix(tmp_path: Path) -> None:
    path = tmp_path / "z.csv"
    path.write_text(
        "timestamp,open,high,low,close,tick_volume,spread\n"
        "2025-03-03T00:00:00Z,2000.0,2001.0,1999.0,2000.5,10,20\n",
        encoding="utf-8",
    )
    out = FileBarSource(path, symbol="XAUUSD", timeframe=Timeframe.M15).fetch_bars(WIDE)
    assert out["timestamp"][0] == datetime(2025, 3, 3, 0, 0, tzinfo=UTC)


def test_mt5_connect_failure_surfaces_terminal_error() -> None:
    class Failing(FakeMt5):
        def initialize(self, **kwargs: object) -> bool:
            return False

    src = Mt5BarSource(Failing(None), Mt5Settings(broker_timezone="UTC"))
    with pytest.raises(RuntimeError, match="initialize failed"):
        src.connect()


def test_mt5_missing_timeframe_constant_raises() -> None:
    class NoConstants:
        def copy_rates_range(self, *args: object) -> None:
            raise AssertionError

        def last_error(self) -> tuple[int, str]:
            return (0, "")

        def initialize(self, **kwargs: object) -> bool:
            return True

        def shutdown(self) -> None:
            return None

    src = Mt5BarSource(NoConstants(), Mt5Settings(broker_timezone="UTC"))
    with pytest.raises(RuntimeError, match="no constant"):
        src.fetch_bars(request())
