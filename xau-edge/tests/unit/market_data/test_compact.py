"""Compaction keeps the merged content identical, archives (never deletes) and is idempotent."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import polars as pl
import pytest

from tests.conftest import make_bars
from xau_edge.domain.timeframe import Timeframe
from xau_edge.market_data.catalog import DatasetCatalog, clear_catalog_cache
from xau_edge.market_data.compact import CompactionError, compact_all, compact_timeframe
from xau_edge.market_data.store import RawDataIntegrityError, RawStore, dataframe_sha256

pytestmark = pytest.mark.unit

TF = Timeframe.H4
START = datetime(2025, 1, 25, tzinfo=UTC)  # spans a month boundary with 6 bars/day


def fragmented(tmp_path: Path, fetches: int = 12) -> RawStore:
    store = RawStore(tmp_path / "raw")
    for i in range(fetches):
        # sliding, overlapping fetches; later ones differ on the overlap so "newest wins" matters
        frame = make_bars(10, timeframe=TF, start=START + i * 3 * TF.delta, base=2000.0 + i)
        store.write(
            frame,
            symbol="XAUUSD",
            timeframe=TF,
            source="mt5",
            fetched_at=datetime(2025, 2, 1, tzinfo=UTC) + timedelta(minutes=i),
        )
    return store


def test_compaction_preserves_merged_content_and_archives_old_files(tmp_path: Path) -> None:
    store = fragmented(tmp_path)
    catalog = DatasetCatalog(tmp_path / "raw")
    before = catalog.load("XAUUSD", TF)
    old_names = {d.path.name for d in before.datasets}

    result = compact_timeframe(tmp_path / "raw", "XAUUSD", TF, now=datetime(2025, 3, 1, tzinfo=UTC))

    assert result.files_before == 12
    assert result.files_after == 2  # January and February
    assert result.archived == 12
    after = catalog.load("XAUUSD", TF)
    assert dataframe_sha256(after.frame) == dataframe_sha256(before.frame)
    assert after.dataset_id != before.dataset_id
    assert all(store.verify(d) for d in store.datasets("XAUUSD", TF))
    # nothing deleted: every old parquet + sidecar sits in the archive, with a manifest
    assert result.archive_dir is not None
    archived = {p.name for p in result.archive_dir.glob("*.parquet")}
    assert archived == old_names
    assert len(list(result.archive_dir.glob("*.meta.json"))) == 12
    manifest = json.loads((result.archive_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["old_dataset_id"] == before.dataset_id
    assert manifest["merged_frame_sha256"] == dataframe_sha256(before.frame)


def test_archive_folder_is_invisible_to_the_catalog(tmp_path: Path) -> None:
    fragmented(tmp_path)
    compact_timeframe(tmp_path / "raw", "XAUUSD", TF)
    assert DatasetCatalog(tmp_path / "raw").available() == [("XAUUSD", TF)]


def test_second_run_is_a_no_op(tmp_path: Path) -> None:
    fragmented(tmp_path)
    compact_timeframe(tmp_path / "raw", "XAUUSD", TF)
    again = compact_timeframe(tmp_path / "raw", "XAUUSD", TF)
    assert again.archived == 0
    assert again.skipped_reason == "already compact"
    assert len(list((tmp_path / "raw" / "_archive" / "XAUUSD" / TF.value).iterdir())) == 1


def test_new_refresh_after_compaction_still_wins_on_overlap(tmp_path: Path) -> None:
    store = fragmented(tmp_path)
    compact_timeframe(tmp_path / "raw", "XAUUSD", TF)
    late = make_bars(2, timeframe=TF, start=START, base=9999.0)
    store.write(
        late,
        symbol="XAUUSD",
        timeframe=TF,
        source="mt5",
        fetched_at=datetime(2025, 3, 5, tzinfo=UTC),
    )
    frame = DatasetCatalog(tmp_path / "raw").load("XAUUSD", TF).frame
    assert frame.filter(pl.col("timestamp") == START)["open"][0] == pytest.approx(9999.0)


def test_dry_run_and_min_files_change_nothing(tmp_path: Path) -> None:
    fragmented(tmp_path, fetches=3)
    root = tmp_path / "raw"
    names = sorted(p.name for p in (root / "XAUUSD" / TF.value).iterdir())
    dry = compact_timeframe(root, "XAUUSD", TF, dry_run=True)
    assert dry.dry_run
    assert dry.files_after == 1
    few = compact_timeframe(root, "XAUUSD", TF, min_files=10)
    assert few.skipped_reason is not None
    assert names == sorted(p.name for p in (root / "XAUUSD" / TF.value).iterdir())
    assert not (root / "_archive").exists()


def test_tampered_source_blocks_compaction(tmp_path: Path) -> None:
    store = fragmented(tmp_path, fetches=3)
    victim = store.datasets("XAUUSD", TF)[0]
    victim.path.chmod(0o666)
    make_bars(10, timeframe=TF, base=1.0).write_parquet(victim.path)
    clear_catalog_cache()
    with pytest.raises(RawDataIntegrityError):
        compact_timeframe(tmp_path / "raw", "XAUUSD", TF)
    assert not (tmp_path / "raw" / "_archive").exists()


def test_failed_equivalence_check_moves_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fragmented(tmp_path, fetches=3)
    real = dataframe_sha256
    calls = {"n": 0}

    def flaky(df: pl.DataFrame) -> str:
        calls["n"] += 1
        return real(df) if calls["n"] % 2 else "different"

    monkeypatch.setattr("xau_edge.market_data.compact.dataframe_sha256", flaky)
    with pytest.raises(CompactionError):
        compact_timeframe(tmp_path / "raw", "XAUUSD", TF)
    assert not (tmp_path / "raw" / "_archive").exists()
    assert len(list((tmp_path / "raw" / "XAUUSD" / TF.value).glob("mt5__*.parquet"))) == 3


def test_compact_all_covers_every_timeframe(tmp_path: Path) -> None:
    fragmented(tmp_path)
    store = RawStore(tmp_path / "raw")
    for i in range(3):
        store.write(
            make_bars(5, start=START + timedelta(hours=i)),
            symbol="XAUUSD",
            timeframe=Timeframe.M15,
            source="mt5",
            fetched_at=datetime(2025, 2, 1, tzinfo=UTC) + timedelta(minutes=i),
        )
    results = compact_all(tmp_path / "raw")
    assert {r.timeframe for r in results} == {TF, Timeframe.M15}
