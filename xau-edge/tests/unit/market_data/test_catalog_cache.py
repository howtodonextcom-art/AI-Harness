"""The catalog caches its merge by file signature and stays correct when files change."""

from __future__ import annotations

import stat
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from tests.conftest import make_bars
from xau_edge.domain.timeframe import Timeframe
from xau_edge.market_data import catalog as catalog_mod
from xau_edge.market_data.catalog import DatasetCatalog, clear_catalog_cache
from xau_edge.market_data.store import RawDataIntegrityError, RawStore

pytestmark = pytest.mark.unit

TF = Timeframe.M15
T1 = datetime(2026, 1, 1, tzinfo=UTC)
T2 = datetime(2026, 2, 1, tzinfo=UTC)


def test_repeated_load_does_not_reread_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = RawStore(tmp_path / "raw")
    store.write(make_bars(10), symbol="XAUUSD", timeframe=TF, source="a", fetched_at=T1)
    first = DatasetCatalog(tmp_path / "raw").load("XAUUSD", TF)

    def boom(*_a: object, **_k: object) -> None:
        msg = "cache miss"
        raise AssertionError(msg)

    monkeypatch.setattr(RawStore, "read_verified", boom)
    again = DatasetCatalog(tmp_path / "raw").load("XAUUSD", TF)  # a NEW instance, as the bot does
    assert again is first


def test_new_file_invalidates_the_cache(tmp_path: Path) -> None:
    store = RawStore(tmp_path / "raw")
    store.write(make_bars(10), symbol="XAUUSD", timeframe=TF, source="a", fetched_at=T1)
    catalog = DatasetCatalog(tmp_path / "raw")
    first = catalog.load("XAUUSD", TF)
    store.write(
        make_bars(10, base=5.0, start=first.frame["timestamp"][-1]),
        symbol="XAUUSD",
        timeframe=TF,
        source="b",
        fetched_at=T2,
    )
    second = catalog.load("XAUUSD", TF)
    assert second.dataset_id != first.dataset_id
    assert second.frame.height == 19


def test_tampering_after_a_cached_load_is_detected(tmp_path: Path) -> None:
    store = RawStore(tmp_path / "raw")
    ds = store.write(make_bars(10), symbol="XAUUSD", timeframe=TF, source="a", fetched_at=T1)
    catalog = DatasetCatalog(tmp_path / "raw")
    catalog.load("XAUUSD", TF)
    ds.path.chmod(stat.S_IWRITE | stat.S_IREAD)
    make_bars(12, base=1.0).write_parquet(ds.path)
    with pytest.raises(RawDataIntegrityError):
        catalog.load("XAUUSD", TF)


def test_use_cache_false_forces_full_verification(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = RawStore(tmp_path / "raw")
    store.write(make_bars(10), symbol="XAUUSD", timeframe=TF, source="a", fetched_at=T1)
    catalog = DatasetCatalog(tmp_path / "raw")
    catalog.load("XAUUSD", TF)
    calls = {"n": 0}
    real = RawStore.read_verified

    def counting(self: RawStore, dataset: Any) -> Any:
        calls["n"] += 1
        return real(self, dataset)

    monkeypatch.setattr(RawStore, "read_verified", counting)
    catalog.load("XAUUSD", TF, use_cache=False)
    assert calls["n"] == 1


def test_cache_is_bounded(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    clear_catalog_cache()
    monkeypatch.setattr(catalog_mod, "CACHE_MAX_ENTRIES", 2)
    store = RawStore(tmp_path / "raw")
    for tf in (Timeframe.M5, Timeframe.M15, Timeframe.H1):
        frame = make_bars(5, timeframe=tf)
        store.write(frame, symbol="XAUUSD", timeframe=tf, source="a", fetched_at=T1)
        DatasetCatalog(tmp_path / "raw").load("XAUUSD", tf)
    assert len(catalog_mod._CACHE) <= 2
