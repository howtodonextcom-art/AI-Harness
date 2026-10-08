"""Versioned feature set: schema, determinism, causality, storage keyed by dataset id."""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path

import numpy as np
import polars as pl
import pytest

from tests.conftest import make_bars
from xau_edge.domain.timeframe import Timeframe
from xau_edge.features.feature_set import (
    FeatureConfig,
    FeatureStore,
    build_features,
    feature_id,
)
from xau_edge.features.indicators import atr as atr_fn


def _noisy(n: int = 400, timeframe: Timeframe = Timeframe.M15) -> pl.DataFrame:
    rng = np.random.default_rng(11)
    base = make_bars(n, timeframe)
    close = 2000 + np.cumsum(rng.normal(0, 2, n))
    open_ = np.concatenate([[2000.0], close[:-1]])
    high = np.maximum(open_, close) + np.abs(rng.normal(0, 1, n))
    low = np.minimum(open_, close) - np.abs(rng.normal(0, 1, n))
    return base.with_columns(
        pl.Series("open", open_),
        pl.Series("high", high),
        pl.Series("low", low),
        pl.Series("close", close),
        pl.Series("tick_volume", rng.integers(50, 500, n)),
    )


EXPECTED_COLUMNS = {
    "timestamp",
    "available_at",
    "gap_before",
    "ret_1",
    "log_ret_1",
    "ret_5",
    "ret_10",
    "ret_20",
    "ema_9",
    "ema_20",
    "ema_50",
    "ema_200",
    "adx_14",
    "plus_di_14",
    "minus_di_14",
    "rsi_14",
    "macd",
    "macd_signal",
    "macd_hist",
    "stoch_k",
    "stoch_d",
    "atr_14",
    "bb_upper",
    "bb_middle",
    "bb_lower",
    "vol_20",
    "range_atr",
    "body_size",
    "upper_wick",
    "lower_wick",
    "body_range",
    "body_atr",
    "upper_wick_atr",
    "lower_wick_atr",
    "tick_volume",
    "volume_zscore",
    "volume_change",
    "hour",
    "day_of_week",
    "trading_session",
}


def test_schema_has_every_feature_group_from_the_brief() -> None:
    out = build_features(_noisy(), Timeframe.M15)
    assert set(out.columns) == EXPECTED_COLUMNS
    assert out.height == 400


def test_available_at_is_bar_close_time() -> None:
    bars = _noisy(50, Timeframe.H1)
    out = build_features(bars, Timeframe.H1)
    diff = (out["available_at"] - out["timestamp"]).unique().to_list()
    assert diff == [timedelta(hours=1)]


def test_warmup_rows_are_null_not_nan() -> None:
    out = build_features(_noisy(), Timeframe.M15)
    assert out["ema_200"].null_count() == 199
    assert out["ema_200"].is_nan().sum() == 0
    assert out["ret_1"][0] is None
    assert out["ema_9"][8] is not None
    assert out["ema_9"][7] is None


def test_output_is_deterministic() -> None:
    bars = _noisy()
    a = build_features(bars, Timeframe.M15)
    b = build_features(bars.clone(), Timeframe.M15)
    assert a.equals(b)


def test_features_never_use_future_bars() -> None:
    bars = _noisy(300)
    full = build_features(bars, Timeframe.M15)
    for cut in (120, 250):
        part = build_features(bars.head(cut), Timeframe.M15)
        assert full.head(cut).equals(part), f"features changed when bars after {cut} were removed"


def test_candle_ratios_use_the_same_atr_column() -> None:
    bars = _noisy()
    out = build_features(bars, Timeframe.M15)
    atr = atr_fn(bars["high"].to_numpy(), bars["low"].to_numpy(), bars["close"].to_numpy(), 14)
    row = 100
    body = abs(bars["close"][row] - bars["open"][row])
    assert out["body_atr"][row] == pytest.approx(body / atr[row])
    assert out["atr_14"][row] == pytest.approx(atr[row])


def test_config_changes_columns_and_id() -> None:
    bars = _noisy()
    cfg = FeatureConfig(ema_periods=(5, 10))
    out = build_features(bars, Timeframe.M15, cfg)
    assert "ema_5" in out.columns
    assert "ema_9" not in out.columns
    assert feature_id("d1", Timeframe.M15, cfg) != feature_id("d1", Timeframe.M15)


def test_feature_id_depends_on_dataset_timeframe_version_and_is_stable() -> None:
    a = feature_id("d1", Timeframe.M15)
    assert a == feature_id("d1", Timeframe.M15)
    assert a != feature_id("d2", Timeframe.M15)
    assert a != feature_id("d1", Timeframe.H1)
    assert len(a) == 16


@pytest.mark.parametrize(
    "mutate",
    [
        lambda df: df.reverse(),
        lambda df: pl.concat([df.head(5), df.head(1), df.tail(df.height - 5)]),
        lambda df: pl.concat([df.head(5), df.slice(4, 1), df.tail(df.height - 5)]),
        lambda df: df.with_columns(pl.col("timestamp").dt.replace_time_zone(None)),
        lambda df: df.drop("close"),
        lambda df: df.clear(),
    ],
)
def test_unsorted_duplicate_naive_or_incomplete_bars_are_rejected(mutate: object) -> None:
    bars = _noisy(40)
    with pytest.raises(ValueError, match=r"timestamp|column|empty|sorted|unique|UTC"):
        build_features(mutate(bars), Timeframe.M15)  # type: ignore[operator]


def test_short_series_gives_all_null_indicator_columns() -> None:
    out = build_features(_noisy(5), Timeframe.M15)
    assert out.height == 5
    assert out["ema_200"].null_count() == 5


def test_store_roundtrip_and_immutability(tmp_path: Path) -> None:
    store = FeatureStore(tmp_path)
    frame = build_features(_noisy(60), Timeframe.M15)
    ref = store.write(frame, symbol="XAUUSD", timeframe=Timeframe.M15, dataset_id="abc")
    assert ref.feature_id == feature_id("abc", Timeframe.M15)
    assert ref.rows == 60
    again = store.write(frame, symbol="XAUUSD", timeframe=Timeframe.M15, dataset_id="abc")
    assert again.path == ref.path
    assert store.read(ref).equals(frame)


def test_store_refuses_different_content_under_the_same_id(tmp_path: Path) -> None:
    store = FeatureStore(tmp_path)
    frame = build_features(_noisy(60), Timeframe.M15)
    store.write(frame, symbol="XAUUSD", timeframe=Timeframe.M15, dataset_id="abc")
    other = frame.with_columns(pl.col("ema_9") + 1)
    with pytest.raises(ValueError, match="different content"):
        store.write(other, symbol="XAUUSD", timeframe=Timeframe.M15, dataset_id="abc")


def test_store_detects_tampering(tmp_path: Path) -> None:
    store = FeatureStore(tmp_path)
    frame = build_features(_noisy(60), Timeframe.M15)
    ref = store.write(frame, symbol="XAUUSD", timeframe=Timeframe.M15, dataset_id="abc")
    ref.path.chmod(0o666)
    frame.with_columns(pl.col("ema_9") * 2).write_parquet(ref.path)
    with pytest.raises(ValueError, match="hash"):
        store.read(ref)


def test_store_rejects_unsafe_names(tmp_path: Path) -> None:
    frame = build_features(_noisy(20), Timeframe.M15)
    with pytest.raises(ValueError, match="symbol"):
        FeatureStore(tmp_path).write(
            frame, symbol="../x", timeframe=Timeframe.M15, dataset_id="abc"
        )
    with pytest.raises(ValueError, match="dataset_id"):
        FeatureStore(tmp_path).write(
            frame, symbol="XAUUSD", timeframe=Timeframe.M15, dataset_id="a/b"
        )


def test_return_columns_are_simple_and_log_returns() -> None:
    bars = _noisy(30)
    out = build_features(bars, Timeframe.M15)
    c = bars["close"]
    assert out["ret_1"][5] == pytest.approx(c[5] / c[4] - 1)
    assert out["log_ret_1"][5] == pytest.approx(float(np.log(c[5] / c[4])))
    assert out["ret_5"][10] == pytest.approx(c[10] / c[5] - 1)


def test_feature_id_changes_with_the_feature_set_version(monkeypatch: pytest.MonkeyPatch) -> None:
    before = feature_id("d1", Timeframe.M15)
    monkeypatch.setattr("xau_edge.features.feature_set.FEATURE_SET_VERSION", "999")
    assert feature_id("d1", Timeframe.M15) != before


def test_gap_before_marks_bars_after_a_missing_stretch() -> None:
    bars = _noisy(30)
    gapped = pl.concat([bars.head(10), bars.slice(14, 16)])  # 4 bars missing
    out = build_features(gapped, Timeframe.M15)
    flags = out["gap_before"].to_list()
    assert flags[10] is True
    assert flags.count(True) == 1
    assert flags[0] is False
    assert out["gap_before"].null_count() == 0


def test_store_read_rejects_refs_outside_the_root(tmp_path: Path) -> None:
    frame = build_features(_noisy(20), Timeframe.M15)
    inside = FeatureStore(tmp_path / "a")
    ref = inside.write(frame, symbol="XAUUSD", timeframe=Timeframe.M15, dataset_id="abc")
    with pytest.raises(ValueError, match="outside"):
        FeatureStore(tmp_path / "b").read(ref)


def test_store_rejects_windows_reserved_dataset_ids(tmp_path: Path) -> None:
    frame = build_features(_noisy(20), Timeframe.M15)
    with pytest.raises(ValueError, match="dataset_id"):
        FeatureStore(tmp_path).write(
            frame, symbol="XAUUSD", timeframe=Timeframe.M15, dataset_id="NUL"
        )
