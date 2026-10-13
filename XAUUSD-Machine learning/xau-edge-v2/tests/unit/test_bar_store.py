from __future__ import annotations

import os
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

import polars as pl
from hypothesis import given, settings
from hypothesis import strategies as st

from tests.conftest import write_series
from xau_edge_v2.data.bar_store import BarStore
from xau_edge_v2.domain.contract import Timeframe

START = datetime(2026, 1, 28, 0, 0, tzinfo=UTC)  # spans three monthly files (Jan, Feb, Mar)
COUNT = 24 * 60  # H1 every hour: ~60 days
TF = Timeframe.H1


def _store(tmp_path: Path) -> tuple[BarStore, list[datetime]]:
    times = write_series(tmp_path / "m", TF, START, COUNT, step_minutes=60)
    return BarStore(tmp_path / "m", cache_seconds=0.0), times


def test_tail_is_the_newest_n_ascending(tmp_path: Path) -> None:
    store, times = _store(tmp_path)
    frame = store.tail(TF, 10)
    assert frame["timestamp"].to_list() == times[-10:]
    assert store.tail(TF, 10).height == 10


def test_tail_before_is_strictly_before(tmp_path: Path) -> None:
    store, times = _store(tmp_path)
    cut = times[500]
    frame = store.tail(TF, 5, before=cut)
    assert frame["timestamp"].to_list() == times[495:500]  # the bar AT cut is excluded


def test_window_is_half_open_and_limited(tmp_path: Path) -> None:
    store, times = _store(tmp_path)
    a, b = times[100], times[110]
    assert store.window(TF, a, b, 1000)["timestamp"].to_list() == times[100:110]
    assert store.window(TF, a, None, 4)["timestamp"].to_list() == times[100:104]
    assert store.window(TF, times[-1] + timedelta(hours=1), None, 5).height == 0


def test_paging_back_with_before_covers_history_exactly_once(tmp_path: Path) -> None:
    store, times = _store(tmp_path)
    seen: list[datetime] = []
    cursor: datetime | None = None
    for _ in range(10_000):
        page = store.tail(TF, 97, before=cursor)
        if page.height == 0:
            break
        seen = page["timestamp"].to_list() + seen
        cursor = page["timestamp"][0]
    assert seen == times  # complete, ascending, no duplicates, no gaps


@settings(deadline=None, max_examples=40)
@given(st.integers(min_value=1, max_value=400), st.integers(min_value=0, max_value=COUNT - 1))
def test_any_page_is_a_contiguous_slice(limit: int, index: int) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        times = write_series(Path(tmp) / "m", TF, START, COUNT, step_minutes=60)
        store = BarStore(Path(tmp) / "m", cache_seconds=0.0)
        cut = times[index]
        got = store.tail(TF, limit, before=cut)["timestamp"].to_list()
        assert got == times[max(0, index - limit) : index]


def test_first_stored_bar_wins_on_duplicate_open_time(tmp_path: Path) -> None:
    root = tmp_path / "m"
    times = write_series(root, TF, START, 10, step_minutes=60)
    path = root / "XAUUSD" / "H1" / "2026-01.parquet"
    frame = pl.read_parquet(path)
    dup = frame.head(1).with_columns(pl.lit(999.0).alias("open"))
    pl.concat([frame, dup]).write_parquet(path)
    got = BarStore(root, cache_seconds=0.0).tail(TF, 100)
    assert got["timestamp"].to_list() == times and got["open"][0] != 999.0


def test_coverage_and_cache_invalidation(tmp_path: Path) -> None:
    store, times = _store(tmp_path)
    cov = store.coverage(TF)
    assert (cov.oldest, cov.newest, cov.files) == (times[0], times[-1], 3)
    write_series(tmp_path / "m", TF, times[-1] + timedelta(hours=1), 5, step_minutes=60)
    assert store.coverage(TF).newest == times[-1] + timedelta(hours=5)  # ttl 0: picks up appends


def test_empty_and_missing_store(tmp_path: Path) -> None:
    store = BarStore(tmp_path / "nothing")
    assert not store.reachable()
    assert store.tail(TF, 5).height == 0 and store.window(TF, START, None, 5).height == 0
    assert store.coverage(TF).newest is None


def test_reading_never_changes_the_store(tmp_path: Path) -> None:
    store, _ = _store(tmp_path)

    def snap() -> dict[str, tuple[int, float]]:
        return {
            str(p): (p.stat().st_size, p.stat().st_mtime)
            for p in sorted((tmp_path / "m").rglob("*"))
        }

    before = snap()
    for _ in range(3):
        store.tail(TF, 50)
        store.window(TF, START, None, 50)
        store.coverage(TF)
    assert snap() == before


def test_works_on_a_read_only_store(tmp_path: Path) -> None:
    store, times = _store(tmp_path)
    files = list((tmp_path / "m").rglob("*.parquet"))
    for f in files:
        os.chmod(f, 0o444)
    try:
        assert store.tail(TF, 3)["timestamp"].to_list() == times[-3:]
    finally:
        for f in files:
            os.chmod(f, 0o666)
