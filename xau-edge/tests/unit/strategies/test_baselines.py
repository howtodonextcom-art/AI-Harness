"""Baseline strategies A and B: deterministic signals from fixed rules."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import polars as pl
import pytest

from xau_edge.strategies.baselines import (
    SIGNAL_COLUMNS,
    BaselineAConfig,
    BaselineBConfig,
    baseline_a,
    baseline_b,
)
from xau_edge.strategies.context import align_to

T0 = datetime(2025, 3, 3, 0, 0, tzinfo=UTC)


def _frame(minutes: int, n: int, **cols: list[Any]) -> pl.DataFrame:
    ts = [T0 + timedelta(minutes=minutes * i) for i in range(n)]
    return pl.DataFrame(
        {
            "timestamp": pl.Series(ts, dtype=pl.Datetime("us", "UTC")),
            "available_at": pl.Series(
                [t + timedelta(minutes=minutes) for t in ts], dtype=pl.Datetime("us", "UTC")
            ),
            **cols,
        }
    )


# ---- alignment ------------------------------------------------------------------------------


def test_align_uses_only_higher_timeframe_bars_that_have_closed() -> None:
    base = _frame(5, 24, x=list(range(24)))
    h1 = _frame(60, 2, trend=[1, -1])
    out = align_to(base, h1, ["trend"], prefix="h1_")
    # H1 bar 0 closes at 01:00 = base index 11's available_at (12 x 5 min); before that: null
    assert out["h1_trend"][:11].null_count() == 11
    assert out["h1_trend"][11] == 1  # decision time 01:00 may use the H1 bar that just closed
    assert out["h1_trend"][22] == 1  # H1 bar 1 closes at 02:00, base index 23
    assert out["h1_trend"][23] == -1


def test_aligned_row_never_comes_from_the_future() -> None:
    base = _frame(15, 40, x=list(range(40)))
    h4 = _frame(240, 3, marker=[10, 20, 30])
    out = align_to(base, h4, ["marker", "available_at"], prefix="h4_").drop_nulls("h4_available_at")
    assert out.height > 0
    assert (out["h4_available_at"] <= out["available_at"]).all()
    # and it is the LATEST closed bar: the next one would not have closed yet
    assert (out["h4_available_at"] + timedelta(hours=4) > out["available_at"]).all()


def test_align_rejects_missing_columns() -> None:
    with pytest.raises(ValueError, match="column"):
        align_to(_frame(5, 3), _frame(60, 1), ["trend"], prefix="h_")


# ---- baseline A -----------------------------------------------------------------------------


def _a_inputs(trend: int, rsi: float, bos: int, choch: int = 0):  # type: ignore[no-untyped-def]
    n = 24
    m5 = _frame(5, n, bos=[0] * 23 + [bos], choch=[0] * 23 + [choch], atr_14=[2.0] * n)
    m15 = _frame(15, 8, rsi_14=[rsi] * 8)
    h1 = _frame(60, 2, trend=[trend] * 2)
    return m5, m15, h1


def test_baseline_a_goes_long_on_h1_uptrend_m15_pullback_and_m5_break_up() -> None:
    sig = baseline_a(*_a_inputs(trend=1, rsi=40.0, bos=1))
    assert sig.columns == list(SIGNAL_COLUMNS)
    assert sig["direction"].to_list() == [1]
    assert sig["atr"][0] == 2.0
    assert sig["stop_atr"][0] == 1.5
    assert sig["target_atr"][0] == 3.0


def test_baseline_a_goes_short_on_the_mirror_conditions() -> None:
    sig = baseline_a(*_a_inputs(trend=-1, rsi=60.0, bos=0, choch=-1))
    assert sig["direction"].to_list() == [-1]


@pytest.mark.parametrize(
    ("trend", "rsi", "bos"),
    [(0, 40.0, 1), (-1, 40.0, 1), (1, 50.0, 1), (1, 40.0, 0), (1, 46.0, 1)],
)
def test_baseline_a_waits_when_any_condition_fails(trend: int, rsi: float, bos: int) -> None:
    assert baseline_a(*_a_inputs(trend=trend, rsi=rsi, bos=bos)).height == 0


def test_baseline_a_rsi_thresholds_are_inclusive() -> None:
    assert baseline_a(*_a_inputs(trend=1, rsi=45.0, bos=1)).height == 1
    assert baseline_a(*_a_inputs(trend=-1, rsi=55.0, bos=-1)).height == 1


def test_baseline_a_cooldown_suppresses_repeats() -> None:
    n = 40
    m5 = _frame(5, n, bos=[1] * n, choch=[0] * n, atr_14=[2.0] * n)
    m15 = _frame(15, 14, rsi_14=[40.0] * 14)
    h1 = _frame(60, 4, trend=[1] * 4)
    cfg = BaselineAConfig(cooldown_bars=12)
    sig = baseline_a(m5, m15, h1, cfg)
    gaps = sig["timestamp"].diff().drop_nulls().dt.total_minutes().to_list()
    assert all(g >= 12 * 5 for g in gaps)
    assert sig.height >= 2


def test_baseline_a_needs_higher_timeframe_data_to_be_available() -> None:
    _, m15, h1 = _a_inputs(trend=1, rsi=40.0, bos=1)
    m5 = _frame(5, 8, bos=[1] * 8, choch=[0] * 8, atr_14=[2.0] * 8)  # all before the first H1 close
    assert baseline_a(m5, m15, h1).height == 0


# ---- baseline B -----------------------------------------------------------------------------


def _b_frame(
    ema9: list[float], ema20: list[float], ema50: list[float], rsi: list[float]
) -> pl.DataFrame:
    n = len(ema9)
    return _frame(15, n, ema_9=ema9, ema_20=ema20, ema_50=ema50, rsi_14=rsi, atr_14=[1.5] * n)


def test_baseline_b_enters_on_the_first_bar_all_long_conditions_hold() -> None:
    f = _b_frame([3, 3, 3, 3], [2, 2, 2, 2], [1, 1, 1, 1], [40.0, 55.0, 60.0, 65.0])
    sig = baseline_b(f)
    assert sig["direction"].to_list() == [1]
    assert sig["timestamp"][0] == f["timestamp"][1]  # bar 1: RSI first inside 50..70


def test_baseline_b_short_and_band_edges() -> None:
    f = _b_frame([1, 1, 1], [2, 2, 2], [3, 3, 3], [60.0, 50.0, 40.0])
    sig = baseline_b(f)
    assert sig["direction"].to_list() == [-1]
    assert sig["timestamp"][0] == f["timestamp"][1]  # RSI 50 belongs to the short band 30..50
    up = _b_frame([3, 3], [2, 2], [1, 1], [49.9, 70.0])
    assert baseline_b(up)["direction"].to_list() == [1]  # 70 inclusive
    assert baseline_b(_b_frame([3], [2], [1], [70.1])).height == 0


def test_baseline_b_ignores_bars_with_unavailable_indicators() -> None:
    f = _b_frame([3, 3], [2, 2], [1, 1], [60.0, 60.0]).with_columns(
        pl.lit(None, dtype=pl.Float64).alias("ema_50")
    )
    assert baseline_b(f).height == 0


def test_baseline_b_config_changes_the_exit_distances() -> None:
    f = _b_frame([3, 3], [2, 2], [1, 1], [40.0, 60.0])
    sig = baseline_b(f, BaselineBConfig(stop_atr=1.0, target_atr=2.5, max_hold_bars=10))
    assert sig["stop_atr"][0] == 1.0
    assert sig["target_atr"][0] == 2.5
    assert sig["max_hold_bars"][0] == 10


def test_signals_are_decided_at_bar_close() -> None:
    f = _b_frame([3, 3], [2, 2], [1, 1], [40.0, 60.0])
    sig = baseline_b(f)
    assert sig["decision_time"][0] == f["available_at"][1]
