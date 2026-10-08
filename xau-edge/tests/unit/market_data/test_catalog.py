from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from tests.conftest import make_bars
from xau_edge.domain.timeframe import Timeframe
from xau_edge.market_data.catalog import DatasetCatalog
from xau_edge.market_data.store import RawStore

pytestmark = pytest.mark.unit

TF = Timeframe.M15
T_OLD = datetime(2026, 1, 1, tzinfo=UTC)
T_NEW = datetime(2026, 2, 1, tzinfo=UTC)


def populated(tmp_path: Path) -> tuple[RawStore, DatasetCatalog]:
    store = RawStore(tmp_path / "raw")
    first = make_bars(10)
    second = make_bars(10, start=first["timestamp"][5], base=3000.0)  # overlaps 5 bars
    store.write(first, symbol="XAUUSD", timeframe=TF, source="a", fetched_at=T_OLD)
    store.write(second, symbol="XAUUSD", timeframe=TF, source="b", fetched_at=T_NEW)
    return store, DatasetCatalog(tmp_path / "raw")


def test_load_merges_files_and_latest_fetch_wins_on_overlap(tmp_path: Path) -> None:
    _, catalog = populated(tmp_path)
    result = catalog.load("XAUUSD", TF)
    assert result.frame.height == 15
    assert result.duplicates_resolved == 5
    assert result.frame["timestamp"].is_sorted()
    assert result.frame["timestamp"].n_unique() == 15
    # Row 5 exists in both fetches; the newer fetch (base 3000) must win.
    assert result.frame["open"][5] == pytest.approx(3000.0)
    assert result.frame["open"][4] == pytest.approx(make_bars(10)["open"][4])
    assert len(result.datasets) == 2


def test_dataset_id_is_deterministic_and_changes_with_content(tmp_path: Path) -> None:
    store, catalog = populated(tmp_path)
    first_id = catalog.load("XAUUSD", TF).dataset_id
    assert catalog.load("XAUUSD", TF).dataset_id == first_id
    store.write(
        make_bars(3, base=10.0), symbol="XAUUSD", timeframe=TF, source="c", fetched_at=T_NEW
    )
    assert catalog.load("XAUUSD", TF).dataset_id != first_id


def test_unknown_symbol_or_timeframe_raises(tmp_path: Path) -> None:
    _, catalog = populated(tmp_path)
    with pytest.raises(FileNotFoundError, match="No raw datasets"):
        catalog.load("EURUSD", TF)
    with pytest.raises(FileNotFoundError):
        catalog.load("XAUUSD", Timeframe.H4)


def test_list_available_reports_symbols_and_timeframes(tmp_path: Path) -> None:
    _, catalog = populated(tmp_path)
    assert catalog.available() == [("XAUUSD", Timeframe.M15)]


def test_sql_queries_the_merged_view(tmp_path: Path) -> None:
    _, catalog = populated(tmp_path)
    out = catalog.sql("SELECT count(*) AS n, max(high) AS top FROM bars_xauusd_m15")
    assert out["n"][0] == 15
    assert out["top"][0] > 3000.0


def test_sql_rejects_statements_that_modify_data(tmp_path: Path) -> None:
    _, catalog = populated(tmp_path)
    with pytest.raises(ValueError, match="read-only"):
        catalog.sql("DROP VIEW bars_xauusd_m15")
    with pytest.raises(ValueError, match="read-only"):
        catalog.sql("COPY bars_xauusd_m15 TO 'out.csv'")
