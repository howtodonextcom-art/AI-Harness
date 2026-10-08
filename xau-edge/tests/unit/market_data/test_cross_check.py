from __future__ import annotations

import polars as pl
import pytest

from tests.conftest import make_bars
from xau_edge.market_data.validators.cross_check import cross_check

pytestmark = pytest.mark.unit


def test_identical_frames_match_exactly() -> None:
    bars = make_bars(20)
    report = cross_check(bars, bars.clone())
    assert report.matched == 20
    assert report.exact
    assert report.only_in_derived == 0
    assert report.only_in_reference == 0
    assert report.mismatches == {}


def test_value_differences_are_counted_per_column() -> None:
    ref = make_bars(20)
    derived = ref.with_columns(
        pl.when(pl.int_range(pl.len()) == 3)
        .then(pl.col("close") + 1.0)
        .otherwise(pl.col("close"))
        .alias("close"),
        pl.when(pl.int_range(pl.len()) < 2)
        .then(pl.col("tick_volume") + 5)
        .otherwise(pl.col("tick_volume"))
        .alias("tick_volume"),
    )
    report = cross_check(derived, ref)
    assert report.mismatches == {"close": 1, "tick_volume": 2}
    assert not report.exact
    assert report.sample["close"] == (ref["timestamp"][3],)


def test_price_tolerance_absorbs_tiny_differences() -> None:
    ref = make_bars(10)
    derived = ref.with_columns((pl.col("close") + 0.004).alias("close"))
    assert cross_check(derived, ref, price_tolerance=0.005).exact
    assert cross_check(derived, ref, price_tolerance=0.001).mismatches == {"close": 10}


def test_rows_present_on_only_one_side_are_reported() -> None:
    ref = make_bars(10)
    derived = ref.slice(2)  # derived lacks the first two reference rows
    report = cross_check(derived, ref)
    assert report.matched == 8
    assert report.only_in_reference == 2
    assert report.only_in_derived == 0
    extra = cross_check(ref, ref.slice(0, 6))
    assert extra.only_in_derived == 4


def test_duplicate_timestamps_on_either_side_make_the_comparison_inexact() -> None:
    """ECC review F-08: a repeated row used to fan out the join and still report exact=True."""
    ref = make_bars(10)
    dup_derived = pl.concat([ref, ref.slice(3, 1)])
    report = cross_check(dup_derived, ref)
    assert report.duplicates_in_derived == 1
    assert report.duplicates_in_reference == 0
    assert not report.exact
    assert cross_check(ref, dup_derived).duplicates_in_reference == 1
    assert not cross_check(ref, dup_derived).exact


def test_null_and_nan_prices_compare_equal_to_themselves() -> None:
    """ECC review F-09: the docstring promises null == null; prices used to break that."""
    ref = make_bars(6)
    holes = ref.with_columns(
        pl.when(pl.int_range(pl.len()) == 1).then(None).otherwise(pl.col("close")).alias("close"),
        pl.when(pl.int_range(pl.len()) == 2)
        .then(float("nan"))
        .otherwise(pl.col("high"))
        .alias("high"),
    )
    assert cross_check(holes, holes.clone()).exact


def test_null_versus_value_and_nan_versus_value_are_mismatches() -> None:
    ref = make_bars(6)
    holes = ref.with_columns(
        pl.when(pl.int_range(pl.len()) == 1).then(None).otherwise(pl.col("close")).alias("close"),
        pl.when(pl.int_range(pl.len()) == 2)
        .then(float("nan"))
        .otherwise(pl.col("high"))
        .alias("high"),
    )
    report = cross_check(holes, ref)
    assert report.mismatches == {"close": 1, "high": 1}


def test_columns_can_be_excluded() -> None:
    ref = make_bars(5)
    derived = ref.with_columns(pl.lit(999, dtype=pl.Int64).alias("spread"))
    assert not cross_check(derived, ref).exact
    assert cross_check(derived, ref, columns=("open", "high", "low", "close", "tick_volume")).exact
