from __future__ import annotations

import json
import stat
from datetime import UTC, datetime
from pathlib import Path

import duckdb
import pytest

from tests.conftest import make_bars
from xau_edge.domain.timeframe import Timeframe
from xau_edge.market_data.catalog import SQL_MEMORY_LIMIT, SQL_THREADS, DatasetCatalog
from xau_edge.market_data.store import RawDataIntegrityError, RawStore, dataframe_sha256

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


def test_load_detects_a_tampered_parquet_file(tmp_path: Path) -> None:
    """ECC review F-06: dataset_id must not vouch for bytes that were never checked."""
    store, catalog = populated(tmp_path)
    victim = store.datasets("XAUUSD", TF)[0]
    victim.path.chmod(stat.S_IWRITE | stat.S_IREAD)
    tampered = make_bars(10, base=777.0)
    tampered.write_parquet(victim.path)  # valid Parquet, different content, sidecar unchanged
    with pytest.raises(RawDataIntegrityError, match="does not match"):
        catalog.load("XAUUSD", TF)


def test_load_rejects_unsafe_symbol_names(tmp_path: Path) -> None:
    _, catalog = populated(tmp_path)
    for bad in ("../XAUUSD", "..", "XAU/USD", "NUL", "XAUUSD."):
        with pytest.raises(ValueError, match="unsafe"):
            catalog.load(bad, TF)


def test_sql_has_resource_limits_and_a_timeout(tmp_path: Path) -> None:
    """ECC review F-14: an accidental or hostile query must not hang the process."""
    _, catalog = populated(tmp_path)
    limits = catalog.sql(
        "SELECT current_setting('memory_limit') AS mem, current_setting('threads') AS threads"
    )
    assert limits["threads"][0] == SQL_THREADS
    reference = duckdb.connect(config={"memory_limit": SQL_MEMORY_LIMIT})
    expected_mem = reference.execute("SELECT current_setting('memory_limit')").fetchone()[0]  # type: ignore[index]
    reference.close()
    assert limits["mem"][0] == expected_mem  # the configured cap, not DuckDB's default
    # A query that cannot be answered without scanning (no constant-folding shortcut).
    with pytest.raises(TimeoutError):
        catalog.sql("SELECT sum(hash(i)) FROM range(100000000000) t(i)", timeout_s=0.5)


def test_sql_result_size_is_capped(tmp_path: Path) -> None:
    """Re-review: the memory limit does not bound a huge result set; a row cap does."""
    _, catalog = populated(tmp_path)
    with pytest.raises(ValueError, match="more than 1000 rows"):
        catalog.sql("SELECT * FROM range(5000000)", max_rows=1000)
    assert catalog.sql("SELECT * FROM range(1000)", max_rows=1000).height == 1000


def test_stray_directories_in_the_data_root_do_not_break_the_catalog(tmp_path: Path) -> None:
    """Re-review (3 reviewers): a `.cache` or `_staging` folder must not take down all queries."""
    _, catalog = populated(tmp_path)
    for stray in (".cache", "_staging", ".git", "con"):
        (tmp_path / "raw" / stray).mkdir()
    assert catalog.available() == [("XAUUSD", TF)]
    assert catalog.sql("SELECT count(*) AS n FROM bars_xauusd_m15")["n"][0] == 15


def test_sidecar_must_agree_with_the_file_it_describes(tmp_path: Path) -> None:
    """Re-review: fetched_at picks the winner on overlaps, so the sidecar must be checked."""
    store, catalog = populated(tmp_path)
    victim = store.datasets("XAUUSD", TF)[0]
    meta = victim.path.with_name(victim.path.name + ".meta.json")
    original = meta.read_text(encoding="utf-8")
    meta.chmod(stat.S_IWRITE | stat.S_IREAD)
    for field, value in (
        ("rows", 999),
        ("symbol", "EURUSD"),
        ("start", "2030-01-01T00:00:00+00:00"),
    ):
        record = json.loads(original)
        record[field] = value
        meta.write_text(json.dumps(record), encoding="utf-8")
        with pytest.raises(RawDataIntegrityError, match="sidecar"):
            catalog.load("XAUUSD", TF)
    meta.write_text(original, encoding="utf-8")
    assert catalog.load("XAUUSD", TF).frame.height == 15  # restored sidecar is accepted again


def test_swapping_a_parquet_and_its_sidecar_together_is_detected(tmp_path: Path) -> None:
    store, catalog = populated(tmp_path)
    first, second = store.datasets("XAUUSD", TF)
    # Replace the older file's content with different data and make the sidecar agree with it.
    forged = make_bars(10, base=555.0)
    first.path.chmod(stat.S_IWRITE | stat.S_IREAD)
    forged.write_parquet(first.path)
    meta = first.path.with_name(first.path.name + ".meta.json")
    meta.chmod(stat.S_IWRITE | stat.S_IREAD)
    record = json.loads(meta.read_text(encoding="utf-8"))
    record["sha256"] = dataframe_sha256(forged)
    meta.write_text(json.dumps(record), encoding="utf-8")
    assert second.path.exists()
    with pytest.raises(RawDataIntegrityError, match="file name"):
        catalog.load("XAUUSD", TF)


def test_sql_rejects_statements_that_modify_data(tmp_path: Path) -> None:
    _, catalog = populated(tmp_path)
    with pytest.raises(ValueError, match="read-only"):
        catalog.sql("DROP VIEW bars_xauusd_m15")
    with pytest.raises(ValueError, match="read-only"):
        catalog.sql("COPY bars_xauusd_m15 TO 'out.csv'")
