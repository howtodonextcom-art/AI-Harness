from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from hypothesis import given
from hypothesis import strategies as st
from pydantic import ValidationError

from xau_edge_v2.api.state import unavailable_state
from xau_edge_v2.config import Settings
from xau_edge_v2.domain.contract import (
    READINESS_ORDER,
    ActionCode,
    Bar,
    BarsResponse,
    Readiness,
    StateSnapshot,
    Timeframe,
    readiness_level,
)

T0 = datetime(2026, 1, 5, tzinfo=UTC)


def _bar(i: int) -> Bar:
    return Bar(time=T0 + timedelta(minutes=i), open=1, high=2, low=0.5, close=1.5, tick_volume=1)


def _snap() -> StateSnapshot:
    return unavailable_state(T0, "t", "NO_BARS", "test")


def _resp(bars: tuple[Bar, ...]) -> BarsResponse:
    return BarsResponse(
        timeframe=Timeframe.M1,
        bars=bars,
        oldest_available=T0,
        newest_available=T0,
        has_more_before=False,
        has_more_after=False,
        data_version="t",
    )


def test_readiness_is_a_zero_to_six_lifecycle() -> None:
    assert [readiness_level(r) for r in READINESS_ORDER] == list(range(7))
    assert READINESS_ORDER[0] is Readiness.NEUTRAL and READINESS_ORDER[-1] is Readiness.READY


def test_unavailable_state_is_honest() -> None:
    s = _snap()
    assert s.action is ActionCode.UNAVAILABLE and s.plan is None
    assert s.evidence.value == "UNVALIDATED" and s.mode == "PAPER"


def test_mode_cannot_be_anything_but_paper() -> None:
    with pytest.raises(ValidationError):
        StateSnapshot(**{**_snap().model_dump(), "mode": "LIVE"})
    with pytest.raises(ValidationError):
        Settings(mode="LIVE")  # type: ignore[arg-type]


def test_buy_or_sell_requires_a_plan() -> None:
    with pytest.raises(ValidationError):
        StateSnapshot(**{**_snap().model_dump(), "action": ActionCode.BUY})


def test_readiness_level_must_match() -> None:
    with pytest.raises(ValidationError):
        StateSnapshot(**{**_snap().model_dump(), "readiness_level": 3})


def test_extra_fields_are_rejected() -> None:
    with pytest.raises(ValidationError):
        Bar(time=T0, open=1, high=2, low=0.5, close=1.5, tick_volume=1, foo=1)  # type: ignore[call-arg]


def test_ohlc_violation_rejected() -> None:
    with pytest.raises(ValidationError):
        Bar(time=T0, open=1, high=1.2, low=0.9, close=3, tick_volume=1)


def test_duplicate_bar_time_rejected() -> None:
    with pytest.raises(ValidationError):
        _resp((_bar(0), _bar(1), _bar(1)))


@given(st.lists(st.integers(min_value=0, max_value=10_000), min_size=0, max_size=40, unique=True))
def test_strictly_increasing_bars_always_accepted(offsets: list[int]) -> None:
    assert len(_resp(tuple(_bar(i) for i in sorted(offsets))).bars) == len(offsets)


@given(st.lists(st.integers(min_value=0, max_value=50), min_size=2, max_size=40))
def test_any_non_increasing_series_rejected(offsets: list[int]) -> None:
    ordered = sorted(offsets)
    if len(set(ordered)) == len(ordered):
        return  # already strictly increasing
    with pytest.raises(ValidationError):
        _resp(tuple(_bar(i) for i in ordered))
