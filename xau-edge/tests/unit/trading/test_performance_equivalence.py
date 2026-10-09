"""The performance work must not change a single decision: indexed ``as_of``, snapshot memo and the
shared market state across variants are checked against the plain reference paths."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from tests.unit.trading.helpers import SPEC, m1_series, resample
from xau_edge.domain.timeframe import Timeframe
from xau_edge.ops.priority import default_workers, lower_priority
from xau_edge.trading.baseline import BaselineConfig
from xau_edge.trading.decision_core import SnapshotInputs, comparable, evaluate, evaluate_many
from xau_edge.trading.frames import MultiTfBars, closed_as_of, from_frames
from xau_edge.trading.market_state import SnapshotMemo, StateConfig
from xau_edge.trading.setup_machine import lifecycle

MINUTES = 20_000  # ~14 days: enough H4 history for every snapshot
TFS = {
    Timeframe.M1: 1,
    Timeframe.M5: 5,
    Timeframe.M15: 15,
    Timeframe.M30: 30,
    Timeframe.H1: 60,
    Timeframe.H4: 240,
}


@pytest.fixture(scope="module")
def bars() -> MultiTfBars:
    m1 = m1_series(MINUTES, seed=7, drift=0.01, vol=0.35)
    return from_frames({tf: (m1 if n == 1 else resample(m1, n)) for tf, n in TFS.items()})


def _inputs(bars: MultiTfBars, at: datetime) -> SnapshotInputs:
    m5 = bars.as_of(Timeframe.M5, at)
    assert m5 is not None
    close, spread = float(m5["close"][-1]), float(m5["spread"][-1])
    return SnapshotInputs(
        bars.truncated(at), at, close, close + spread * SPEC.point, spread, SPEC, 10_000.0,
        "UNKNOWN", True, True,
    )  # fmt: skip


def test_indexed_as_of_equals_the_reference_filter(bars: MultiTfBars) -> None:
    m5 = bars.frames[Timeframe.M5]
    first = m5["available_at"][100]
    for offset in (0, 1, 7, 61, 3000, 4000):
        for seconds in (0, 1, 299):
            at = first + timedelta(minutes=offset, seconds=seconds)
            for tf in TFS:
                assert bars.as_of(tf, at).equals(closed_as_of(bars.frames[tf], at))  # type: ignore[union-attr]
    assert bars.as_of(Timeframe.M5, first - timedelta(days=30)).height == 0  # type: ignore[union-attr]


def test_a_frame_that_is_not_sorted_still_gives_the_filter_result() -> None:
    m1 = m1_series(300)
    shuffled = from_frames({Timeframe.M1: m1}).frames[Timeframe.M1].reverse()
    multi = MultiTfBars({Timeframe.M1: shuffled})
    earliest = shuffled["available_at"].min()
    assert isinstance(earliest, datetime)
    at = earliest + timedelta(minutes=100)
    assert multi.as_of(Timeframe.M1, at).equals(closed_as_of(shuffled, at))  # type: ignore[union-attr]


def test_memo_and_shared_state_give_identical_decisions(bars: MultiTfBars) -> None:
    v11 = BaselineConfig(allow_unknown_news=True, version="1.1.0")
    v12 = BaselineConfig(allow_unknown_news=True, version="1.2.0")
    memo = SnapshotMemo()
    closes = bars.frames[Timeframe.M5]["available_at"].to_list()[-900::90]
    assert len(closes) >= 8
    for at in closes:
        inputs = _inputs(bars, at)
        _, plain11 = evaluate(inputs, v11, None)
        _, plain12 = evaluate(inputs, v12, None)
        _, shared = evaluate_many(inputs, {"a": v11, "b": v12}, None, memo)
        assert comparable(shared["a"]) == comparable(plain11)
        assert comparable(shared["b"]) == comparable(plain12)


def test_lifecycle_is_identical_with_and_without_a_memo(bars: MultiTfBars) -> None:
    memo = SnapshotMemo()
    for at in bars.frames[Timeframe.M5]["available_at"].to_list()[-300::60]:
        assert lifecycle(bars, at, memo=memo) == lifecycle(bars, at)


def test_the_memo_is_keyed_by_bar_so_a_new_bar_is_never_served_stale(bars: MultiTfBars) -> None:
    memo = SnapshotMemo()
    at = bars.frames[Timeframe.M5]["available_at"][-200]
    older = memo.get(bars.closed(Timeframe.M15, at), Timeframe.M15, StateConfig())
    newer = memo.get(
        bars.closed(Timeframe.M15, at + timedelta(hours=3)), Timeframe.M15, StateConfig()
    )
    assert older is not None and newer is not None and older.bar_open != newer.bar_open


def test_batch_helpers_are_safe_and_leave_cores_free() -> None:
    assert isinstance(lower_priority(), bool)
    assert 1 <= default_workers() <= 64
