from __future__ import annotations

import os
import stat
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


def test_stored_file_is_read_only(tmp_path: Path) -> None:
    ds = RawStore(tmp_path).write(make_bars(5), symbol="XAUUSD", timeframe=TF, source="unit")
    assert not os.access(ds.path, os.W_OK)


def test_rewriting_identical_data_is_idempotent(tmp_path: Path) -> None:
    store = RawStore(tmp_path)
    df = make_bars(10)
    first = store.write(df, symbol="XAUUSD", timeframe=TF, source="unit")
    second = store.write(df, symbol="XAUUSD", timeframe=TF, source="unit")
    assert first == second
    assert len(list((tmp_path / "XAUUSD" / "M15").iterdir())) == 1


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


def test_hash_is_stable_and_sensitive_to_values() -> None:
    a = make_bars(5)
    assert dataframe_sha256(a) == dataframe_sha256(a.clone())
    changed = a.with_columns(
        pl.when(pl.int_range(pl.len()) == 0).then(1.0).otherwise(pl.col("open")).alias("open")
    )
    assert dataframe_sha256(a) != dataframe_sha256(changed)
