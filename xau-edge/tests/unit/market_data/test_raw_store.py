from __future__ import annotations

import os
import stat
from datetime import UTC, datetime
from pathlib import Path

import polars as pl
import pytest

from tests.conftest import make_bars
from xau_edge.domain.timeframe import Timeframe
from xau_edge.market_data.store import RawDataImmutableError, RawStore, dataframe_sha256

pytestmark = pytest.mark.unit

TF = Timeframe.M15


def test_write_creates_content_addressed_parquet(tmp_path: Path) -> None:
    store = RawStore(tmp_path)
    df = make_bars(10)
    ds = store.write(df, symbol="XAUUSD", timeframe=TF, source="unit")
    assert ds.path.exists()
    assert ds.path.parent == tmp_path / "XAUUSD" / "M15"
    assert ds.rows == 10
    assert ds.sha256 == dataframe_sha256(df)
    assert ds.sha256[:12] in ds.path.name
    assert pl.read_parquet(ds.path).equals(df)


def test_fetch_time_is_recorded_and_survives_idempotent_rewrites(tmp_path: Path) -> None:
    store = RawStore(tmp_path)
    df = make_bars(5)
    t1 = datetime(2026, 1, 1, tzinfo=UTC)
    t2 = datetime(2026, 6, 1, tzinfo=UTC)
    first = store.write(df, symbol="XAUUSD", timeframe=TF, source="unit", fetched_at=t1)
    again = store.write(df, symbol="XAUUSD", timeframe=TF, source="unit", fetched_at=t2)
    assert first.fetched_at == t1
    assert again.fetched_at == t1  # the original record is never rewritten


def test_fetch_time_defaults_to_now_in_utc(tmp_path: Path) -> None:
    ds = RawStore(tmp_path).write(make_bars(5), symbol="XAUUSD", timeframe=TF, source="unit")
    assert ds.fetched_at.tzinfo is not None
    assert abs((datetime.now(UTC) - ds.fetched_at).total_seconds()) < 60


def test_data_written_before_sidecars_existed_gets_a_record_from_file_time(
    tmp_path: Path,
) -> None:
    store = RawStore(tmp_path)
    df = make_bars(5)
    ds = store.write(df, symbol="XAUUSD", timeframe=TF, source="unit")
    meta = ds.path.with_name(ds.path.name + ".meta.json")
    meta.chmod(stat.S_IWRITE | stat.S_IREAD)
    meta.unlink()  # simulate a Sprint 1 file that has no sidecar
    assert store.datasets("XAUUSD", TF) == []  # unrecorded files are not listed
    again = store.write(df, symbol="XAUUSD", timeframe=TF, source="unit")
    assert again.path == ds.path
    assert again.sha256 == ds.sha256
    assert meta.exists()
    assert store.datasets("XAUUSD", TF) == [again]


def test_datasets_lists_in_fetch_order(tmp_path: Path) -> None:
    store = RawStore(tmp_path)
    late = store.write(
        make_bars(5, base=1.0),
        symbol="XAUUSD",
        timeframe=TF,
        source="b",
        fetched_at=datetime(2026, 3, 1, tzinfo=UTC),
    )
    early = store.write(
        make_bars(5, base=2.0),
        symbol="XAUUSD",
        timeframe=TF,
        source="a",
        fetched_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    assert store.datasets("XAUUSD", TF) == [early, late]
    assert store.datasets("XAUUSD", Timeframe.H4) == []


def test_stored_file_is_read_only(tmp_path: Path) -> None:
    ds = RawStore(tmp_path).write(make_bars(5), symbol="XAUUSD", timeframe=TF, source="unit")
    assert not os.access(ds.path, os.W_OK)


def test_rewriting_identical_data_is_idempotent(tmp_path: Path) -> None:
    store = RawStore(tmp_path)
    df = make_bars(10)
    first = store.write(df, symbol="XAUUSD", timeframe=TF, source="unit")
    second = store.write(df, symbol="XAUUSD", timeframe=TF, source="unit")
    assert first == second
    assert len(list((tmp_path / "XAUUSD" / "M15").glob("*.parquet"))) == 1


def test_existing_file_with_different_content_is_never_overwritten(tmp_path: Path) -> None:
    store = RawStore(tmp_path)
    df = make_bars(10)
    ds = store.write(df, symbol="XAUUSD", timeframe=TF, source="unit")
    ds.path.chmod(stat.S_IWRITE | stat.S_IREAD)  # stored files are read-only by default
    ds.path.write_bytes(b"tampered")  # simulate corruption / in-place edit
    with pytest.raises(RawDataImmutableError):
        store.write(df, symbol="XAUUSD", timeframe=TF, source="unit")
    assert ds.path.read_bytes() == b"tampered"  # untouched by the failed write


def test_different_data_gets_different_file(tmp_path: Path) -> None:
    store = RawStore(tmp_path)
    a = store.write(make_bars(10), symbol="XAUUSD", timeframe=TF, source="unit")
    b = store.write(make_bars(10, base=2100.0), symbol="XAUUSD", timeframe=TF, source="unit")
    assert a.path != b.path


def test_verify_detects_tampering(tmp_path: Path) -> None:
    store = RawStore(tmp_path)
    ds = store.write(make_bars(10), symbol="XAUUSD", timeframe=TF, source="unit")
    assert store.verify(ds)
    ds.path.chmod(stat.S_IWRITE | stat.S_IREAD)
    ds.path.write_bytes(b"tampered")
    assert not store.verify(ds)


def test_refuses_empty_frame_and_unsafe_source_names(tmp_path: Path) -> None:
    store = RawStore(tmp_path)
    with pytest.raises(ValueError, match="empty"):
        store.write(make_bars(0), symbol="XAUUSD", timeframe=TF, source="unit")
    with pytest.raises(ValueError, match="source"):
        store.write(make_bars(3), symbol="XAUUSD", timeframe=TF, source="../evil")


def test_read_side_names_are_validated_like_write_side(tmp_path: Path) -> None:
    """ECC review F-15: datasets() must not accept names that write() would refuse."""
    store = RawStore(tmp_path / "root")
    store.write(make_bars(3), symbol="XAUUSD", timeframe=TF, source="unit")
    (tmp_path / "XAUUSD").mkdir()  # sibling directory outside the store root
    with pytest.raises(ValueError, match="unsafe"):
        store.datasets("../XAUUSD", TF)


@pytest.mark.parametrize(
    "bad", ["NUL", "con", "COM1", "lpt9", "XAUUSD.", "XAU USD", "XAUUSD\n", ""]
)
def test_windows_reserved_names_trailing_dots_and_blanks_are_rejected(
    tmp_path: Path, bad: str
) -> None:
    with pytest.raises(ValueError, match="unsafe"):
        RawStore(tmp_path).write(make_bars(3), symbol=bad, timeframe=TF, source="unit")
    with pytest.raises(ValueError, match="unsafe"):
        RawStore(tmp_path).write(make_bars(3), symbol="XAUUSD", timeframe=TF, source=bad)


def test_unreadable_existing_file_is_reported_as_unreadable_not_as_different(
    tmp_path: Path,
) -> None:
    store = RawStore(tmp_path)
    df = make_bars(5)
    ds = store.write(df, symbol="XAUUSD", timeframe=TF, source="unit")
    ds.path.chmod(stat.S_IWRITE | stat.S_IREAD)
    ds.path.write_bytes(b"PAR1")
    with pytest.raises(RawDataImmutableError, match="unreadable"):
        store.write(df, symbol="XAUUSD", timeframe=TF, source="unit")
    assert store.verify(ds) is False


def test_hash_is_stable_and_sensitive_to_values() -> None:
    a = make_bars(5)
    assert dataframe_sha256(a) == dataframe_sha256(a.clone())
    changed = a.with_columns(
        pl.when(pl.int_range(pl.len()) == 0).then(1.0).otherwise(pl.col("open")).alias("open")
    )
    assert dataframe_sha256(a) != dataframe_sha256(changed)
