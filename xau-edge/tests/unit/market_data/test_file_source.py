from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import polars as pl
import pytest

from tests.conftest import MONDAY, make_bars
from xau_edge.domain.bars import BAR_COLUMNS, BarRequest, MissingColumnsError
from xau_edge.domain.timeframe import Timeframe
from xau_edge.market_data.importers.file_source import FileBarSource, UnsupportedFileError

pytestmark = pytest.mark.unit

TF = Timeframe.M15
WIDE = BarRequest(
    symbol="XAUUSD",
    timeframe=TF,
    start=datetime(2025, 1, 1, tzinfo=UTC),
    end=datetime(2026, 1, 1, tzinfo=UTC),
)


def test_reads_parquet_roundtrip(tmp_path: Path) -> None:
    df = make_bars(20)
    path = tmp_path / "bars.parquet"
    df.write_parquet(path)
    out = FileBarSource(path, symbol="XAUUSD", timeframe=TF).fetch_bars(WIDE)
    assert out.columns == list(BAR_COLUMNS)
    assert out.equals(df)


def test_reads_plain_csv_with_iso_timestamps(tmp_path: Path) -> None:
    path = tmp_path / "bars.csv"
    path.write_text(
        "timestamp,open,high,low,close,tick_volume,spread\n"
        "2025-03-03 00:00:00,2000.0,2001.0,1999.0,2000.5,10,20\n"
        "2025-03-03 00:15:00,2000.5,2002.0,2000.0,2001.5,12,22\n",
        encoding="utf-8",
    )
    out = FileBarSource(path, symbol="XAUUSD", timeframe=TF).fetch_bars(WIDE)
    assert out.height == 2
    assert out["timestamp"][0] == MONDAY
    assert out["timestamp"].dtype == pl.Datetime("us", "UTC")
    assert out["real_volume"].null_count() == 2


def test_reads_metatrader_export_format(tmp_path: Path) -> None:
    path = tmp_path / "XAUUSD15.csv"
    path.write_text(
        "<DATE>\t<TIME>\t<OPEN>\t<HIGH>\t<LOW>\t<CLOSE>\t<TICKVOL>\t<VOL>\t<SPREAD>\n"
        "2025.03.03\t00:00:00\t2000.00\t2001.00\t1999.00\t2000.50\t10\t0\t20\n"
        "2025.03.03\t00:15:00\t2000.50\t2002.00\t2000.00\t2001.50\t12\t0\t22\n",
        encoding="utf-8",
    )
    out = FileBarSource(path, symbol="XAUUSD", timeframe=TF).fetch_bars(WIDE)
    assert out.height == 2
    assert out["timestamp"][1] == datetime(2025, 3, 3, 0, 15, tzinfo=UTC)
    assert out["tick_volume"][0] == 10
    assert out["real_volume"][0] == 0


def test_source_timezone_is_converted_to_utc(tmp_path: Path) -> None:
    path = tmp_path / "bars.csv"
    path.write_text(
        "timestamp,open,high,low,close,tick_volume,spread\n"
        "2025-03-03 02:00:00,2000.0,2001.0,1999.0,2000.5,10,20\n",
        encoding="utf-8",
    )
    src = FileBarSource(path, symbol="XAUUSD", timeframe=TF, source_timezone="Europe/Athens")
    out = src.fetch_bars(WIDE)
    # Athens is UTC+2 on 2025-03-03 (winter time).
    assert out["timestamp"][0] == MONDAY


def test_ambiguous_dst_time_raises(tmp_path: Path) -> None:
    path = tmp_path / "bars.csv"
    path.write_text(
        "timestamp,open,high,low,close,tick_volume,spread\n"
        "2025-10-26 03:30:00,2000.0,2001.0,1999.0,2000.5,10,20\n",  # repeated hour in Athens
        encoding="utf-8",
    )
    src = FileBarSource(path, symbol="XAUUSD", timeframe=TF, source_timezone="Europe/Athens")
    with pytest.raises(pl.exceptions.ComputeError):
        src.fetch_bars(WIDE)


def test_request_range_is_start_inclusive_end_exclusive(tmp_path: Path) -> None:
    df = make_bars(20)
    path = tmp_path / "bars.parquet"
    df.write_parquet(path)
    request = BarRequest(
        symbol="XAUUSD",
        timeframe=TF,
        start=df["timestamp"][5],
        end=df["timestamp"][10],
    )
    out = FileBarSource(path, symbol="XAUUSD", timeframe=TF).fetch_bars(request)
    assert out["timestamp"].to_list() == df["timestamp"].slice(5, 5).to_list()


def test_does_not_silently_dedupe_or_sort(tmp_path: Path) -> None:
    df = make_bars(5)
    messy = pl.concat([df.slice(3, 1), df.slice(0, 3), df.slice(3, 1)])
    path = tmp_path / "bars.parquet"
    messy.write_parquet(path)
    out = FileBarSource(path, symbol="XAUUSD", timeframe=TF).fetch_bars(WIDE)
    assert out["timestamp"].to_list() == messy["timestamp"].to_list()


def test_wrong_symbol_or_timeframe_request_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "bars.parquet"
    make_bars(3).write_parquet(path)
    src = FileBarSource(path, symbol="XAUUSD", timeframe=TF)
    with pytest.raises(ValueError, match="symbol"):
        src.fetch_bars(WIDE.model_copy(update={"symbol": "EURUSD"}))
    with pytest.raises(ValueError, match="timeframe"):
        src.fetch_bars(WIDE.model_copy(update={"timeframe": Timeframe.H1}))


def test_missing_columns_are_reported(tmp_path: Path) -> None:
    path = tmp_path / "bars.csv"
    path.write_text("timestamp,open\n2025-03-03 00:00:00,1.0\n", encoding="utf-8")
    with pytest.raises(MissingColumnsError):
        FileBarSource(path, symbol="XAUUSD", timeframe=TF).fetch_bars(WIDE)


def test_unsupported_extension_and_missing_file(tmp_path: Path) -> None:
    other = tmp_path / "bars.xlsx"
    other.write_bytes(b"x")
    with pytest.raises(UnsupportedFileError):
        FileBarSource(other, symbol="XAUUSD", timeframe=TF).fetch_bars(WIDE)
    with pytest.raises(FileNotFoundError):
        FileBarSource(tmp_path / "nope.csv", symbol="XAUUSD", timeframe=TF).fetch_bars(WIDE)


def test_custom_column_mapping(tmp_path: Path) -> None:
    path = tmp_path / "bars.csv"
    path.write_text(
        "t,o,h,l,c,tv,sp\n2025-03-03 00:00:00,2000.0,2001.0,1999.0,2000.5,10,20\n",
        encoding="utf-8",
    )
    src = FileBarSource(
        path,
        symbol="XAUUSD",
        timeframe=TF,
        columns={
            "timestamp": "t",
            "open": "o",
            "high": "h",
            "low": "l",
            "close": "c",
            "tick_volume": "tv",
            "spread": "sp",
        },
    )
    assert src.fetch_bars(WIDE).height == 1
