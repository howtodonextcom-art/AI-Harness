"""End-to-end offline path: file -> source -> raw store -> validator (no MT5, no network)."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import polars as pl
import pytest

from tests.conftest import make_bars
from xau_edge.domain.bars import BarRequest
from xau_edge.domain.timeframe import Timeframe
from xau_edge.market_data.importers.file_source import FileBarSource
from xau_edge.market_data.store import RawStore
from xau_edge.market_data.validators import IssueCode, validate_bars

pytestmark = pytest.mark.integration


def test_offline_pipeline_is_reproducible_and_flags_bad_data(tmp_path: Path) -> None:
    good = make_bars(96, timeframe=Timeframe.M15)
    bad = pl.concat([good, good.slice(10, 2)])  # inject duplicate rows
    csv = tmp_path / "XAUUSD_M15.csv"
    bad.write_csv(csv)

    request = BarRequest(
        symbol="XAUUSD",
        timeframe=Timeframe.M15,
        start=datetime(2025, 1, 1, tzinfo=UTC),
        end=datetime(2026, 1, 1, tzinfo=UTC),
    )
    source = FileBarSource(csv, symbol="XAUUSD", timeframe=Timeframe.M15)

    frame_1 = source.fetch_bars(request)
    frame_2 = source.fetch_bars(request)
    assert frame_1.equals(frame_2)  # deterministic

    store = RawStore(tmp_path / "raw")
    ds_1 = store.write(frame_1, symbol="XAUUSD", timeframe=Timeframe.M15, source="csv")
    ds_2 = store.write(frame_2, symbol="XAUUSD", timeframe=Timeframe.M15, source="csv")
    assert ds_1 == ds_2
    assert store.verify(ds_1)

    report = validate_bars(pl.read_parquet(ds_1.path), Timeframe.M15)
    assert not report.passed
    assert {i.code for i in report.issues} == {
        IssueCode.DUPLICATE_TIMESTAMPS,
        IssueCode.OUT_OF_ORDER,
    }
