"""The descriptive-study data policy and the outcome-free statistics module."""

from __future__ import annotations

import inspect
from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np
import polars as pl
import pytest

from xau_edge.structure import pattern_stats
from xau_edge.structure.descriptive_data import (
    DEV2_END,
    ForbiddenDatasetError,
    block_shuffled_null,
    load_dev2_h1,
    require_descriptive,
)
from xau_edge.structure.detection import PatternDetection, PatternPoint
from xau_edge.structure.reversal import detect_reversals

pytestmark = pytest.mark.unit


@pytest.mark.parametrize("name", ["testH", "holdout", "val2_h1", "ftmo_2025_plus", "live_market"])
def test_locked_reserved_and_forbidden_datasets_are_refused(name: str) -> None:
    with pytest.raises(ForbiddenDatasetError):
        require_descriptive(name)


def test_unknown_datasets_are_refused_by_default() -> None:
    with pytest.raises(ForbiddenDatasetError, match="UNKNOWN"):
        require_descriptive("some_new_file")


def test_only_synthetic_and_the_burned_development_window_are_open() -> None:
    assert require_descriptive("random_walk").classification == "SYNTHETIC"
    assert require_descriptive("dev2_h1").classification == "BURNED"


def test_dev2_loader_never_returns_a_bar_at_or_after_the_window_end(tmp_path: Path) -> None:
    start = datetime(2018, 6, 1, tzinfo=UTC)
    stamps = [start + timedelta(days=i) for i in range(1000)]  # runs well past 2019-01-01
    n = len(stamps)
    price = np.linspace(100, 120, n)
    pl.DataFrame(
        {
            "timestamp": stamps,
            "open": price,
            "high": price + 1,
            "low": price - 1,
            "close": price,
            "spread": np.zeros(n),
        }
    ).write_parquet(tmp_path / "h1.parquet")
    frame = load_dev2_h1(tmp_path / "h1.parquet")
    latest = frame.select(pl.col("timestamp").max()).item()
    assert latest < DEV2_END
    assert latest == datetime(2018, 12, 31, tzinfo=UTC)
    assert frame.columns == ["timestamp", "open", "high", "low", "close"]  # no spread, no future


def test_dev2_loader_refuses_a_file_with_no_development_bars(tmp_path: Path) -> None:
    stamps = [datetime(2020, 1, 1, tzinfo=UTC) + timedelta(hours=i) for i in range(50)]
    price = np.full(50, 100.0)
    pl.DataFrame(
        {"timestamp": stamps, "open": price, "high": price, "low": price, "close": price}
    ).write_parquet(tmp_path / "late.parquet")
    with pytest.raises(ForbiddenDatasetError, match="no Development-2 bars"):
        load_dev2_h1(tmp_path / "late.parquet")


def test_statistics_take_detections_only_and_so_cannot_compute_outcomes() -> None:
    names = {
        name: list(inspect.signature(fn).parameters)
        for name, fn in inspect.getmembers(pattern_stats, inspect.isfunction)
        if not name.startswith("_") and fn.__module__ == pattern_stats.__name__
    }
    assert names["describe"] == ["detections", "n_bars", "timestamps"]
    assert names["overlap_stats"] == ["detections"]
    for params in names.values():  # nothing accepts prices, returns or a future window
        assert not {"close", "high", "low", "prices", "returns", "future"} & set(params)


def test_describe_reports_frequency_timing_and_overlap_without_outcomes() -> None:
    rng = np.random.default_rng(5)
    close = 100 + np.cumsum(rng.normal(0, 0.3, 3000))
    high = close + np.abs(rng.normal(0, 0.1, 3000))
    low = close - np.abs(rng.normal(0, 0.1, 3000))
    found = detect_reversals(high, low, close)
    stamps = [datetime(2012, 1, 1, tzinfo=UTC) + timedelta(hours=i) for i in range(3000)]
    stats = pattern_stats.describe(found, 3000, stamps)
    assert stats["detections"] == len(found) > 10
    assert stats["per_10k_bars"] == pytest.approx(10_000 * len(found) / 3000)
    lag = stats["confirmation_lag_bars"]
    assert isinstance(lag, dict) and lag["min"] >= 3  # a point is never known before its right bars
    per_year = stats["per_year"]
    assert isinstance(per_year, dict) and set(per_year) <= {"2012"}
    forbidden = {"return", "pnl", "win", "hit", "expectancy", "profit"}
    assert not any(any(f in key for f in forbidden) for key in stats)
    assert pattern_stats.describe([], 100)["detections"] == 0


def test_overlap_counts_nested_and_overlapping_spans() -> None:
    def det(first: int, last: int) -> PatternDetection:
        pts = (PatternPoint(label="A", bar=first, price=1.0, confirmed_at=first + 3),)
        return PatternDetection(
            pattern_id=f"{first}-{last}",
            pattern_type="DOUBLE_TOP",
            bias="SHORT",
            points=pts,
            geometry_known_at=first + 3,
            detected_at=last,
            actionable_at=last,
            source_definition="t",
        )

    stats = pattern_stats.overlap_stats([det(0, 50), det(10, 30), det(40, 80), det(100, 120)])
    assert stats == {"detections": 4, "overlapping": 2, "nested": 1, "overlap_rate": 0.5}


def test_block_shuffled_null_keeps_the_bars_and_destroys_the_order() -> None:
    rng = np.random.default_rng(2)
    close = 100 * np.exp(np.cumsum(rng.normal(0, 0.003, 600)))
    high = close * (1 + np.abs(rng.normal(0, 0.001, 600)))
    low = close * (1 - np.abs(rng.normal(0, 0.001, 600)))
    h2, l2, c2 = block_shuffled_null(high, low, close, seed=4, block=48)
    assert len(c2) == len(close) and (h2 >= l2).all() and (c2 > 0).all()
    # same bars, so the same multiset of log-returns; a different order, so a different path
    assert np.sort(np.diff(np.log(c2))) == pytest.approx(np.sort(np.diff(np.log(close))))
    assert not np.allclose(c2, close)
    again = block_shuffled_null(high, low, close, seed=4, block=48)
    assert np.array_equal(again[2], c2)  # deterministic for a seed
    other = block_shuffled_null(high, low, close, seed=5, block=48)
    assert not np.array_equal(other[2], c2)
