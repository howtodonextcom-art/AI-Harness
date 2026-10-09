from __future__ import annotations

from datetime import UTC, datetime, timedelta

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from xau_edge.integrity.events import (
    Bar,
    BreachDetector,
    EventState,
    LevelEvent,
    day_key,
    detect,
    hour_window_key,
    trend_context,
    volatility_compressed,
)

T0 = datetime(2026, 3, 2, 0, 0, tzinfo=UTC)
HOUR = timedelta(hours=1)


def bar(i: int, o: float, h: float, low: float, c: float) -> Bar:
    start = T0 + HOUR * i
    return Bar(start, start + HOUR, o, h, low, c)


def flat_day(day: int, high: float = 10.0, low: float = 0.0) -> list[Bar]:
    """Twenty-four bars that together make a day with the given high and low."""
    bars = []
    for h in range(24):
        i = day * 24 + h
        top = high if h == 5 else 5.0
        bottom = low if h == 6 else 5.0
        bars.append(bar(i, 5.0, top, bottom, 5.0))
    return bars


def run(bars: list[Bar], m: int = 2) -> list[LevelEvent]:
    return detect(bars, window_key=day_key, level_name="PD", accept_bars=m)


def test_a_poke_that_closes_back_inside_is_rejected_at_its_own_close() -> None:
    bars = [*flat_day(0), bar(24, 9.0, 11.0, 8.0, 9.5)]
    events = run(bars)
    assert [e.state for e in events] == [EventState.REJECTED]
    assert events[0].side == "UP"
    assert events[0].decision_time == bars[-1].close_time
    assert events[0].is_causal()


def test_a_breach_that_holds_for_m_bars_is_accepted_not_earlier() -> None:
    bars = [*flat_day(0), bar(24, 9.0, 12.0, 8.0, 11.5), bar(25, 11.5, 12.5, 11.0, 12.0)]
    # after one holding bar the event is still pending
    assert run(bars, m=2) == [e for e in run(bars, m=2) if e.state is EventState.UNRESOLVED]
    bars.append(bar(26, 12.0, 13.0, 11.8, 12.5))
    events = run(bars, m=2)
    assert [e.state for e in events] == [EventState.ACCEPTED]
    assert events[0].decision_time == bars[-1].close_time
    assert events[0].bars_waited == 2


def test_a_pending_breach_is_rejected_when_a_later_close_falls_back() -> None:
    bars = [*flat_day(0), bar(24, 9.0, 12.0, 8.0, 11.5), bar(25, 11.5, 11.8, 9.0, 9.5)]
    events = run(bars, m=3)
    assert [e.state for e in events] == [EventState.REJECTED]
    assert events[0].bars_waited == 1


def test_a_breach_still_waiting_at_the_end_of_data_is_unresolved() -> None:
    bars = [*flat_day(0), bar(24, 9.0, 12.0, 8.0, 11.5)]
    events = run(bars, m=3)
    assert [e.state for e in events] == [EventState.UNRESOLVED]
    assert events[0].is_causal()


def test_the_current_day_is_not_a_level_for_its_own_bars() -> None:
    # day 0 alone: nothing is breached because no day has completed yet
    assert run(flat_day(0)) == []


def test_asia_window_becomes_a_level_only_after_it_ends() -> None:
    key = hour_window_key(0, 7)
    day0 = [bar(i, 5.0, 5.0 + (i == 3) * 3, 5.0 - (i == 4) * 3, 5.0) for i in range(7)]
    after = [bar(7, 5.0, 9.0, 5.0, 5.0)]  # pokes above the Asia high of 8, no: 8 > 9? high=9
    events = detect([*day0, *after], window_key=key, level_name="ASIA", accept_bars=1)
    assert [e.state for e in events] == [EventState.REJECTED]
    inside = detect(day0, window_key=key, level_name="ASIA", accept_bars=1)
    assert inside == []


def test_bars_must_arrive_in_order() -> None:
    det = BreachDetector(day_key, "PD", 1)
    det.step(bar(1, 5, 5, 5, 5))
    with pytest.raises(ValueError, match="increasing"):
        det.step(bar(0, 5, 5, 5, 5))


def test_malformed_bars_are_refused() -> None:
    with pytest.raises(ValueError, match="malformed"):
        Bar(T0, T0, 1, 1, 1, 1)
    with pytest.raises(ValueError, match="outside"):
        Bar(T0, T0 + HOUR, 5, 4, 3, 4)


@st.composite
def series(draw: st.DrawFn) -> list[Bar]:
    n = draw(st.integers(min_value=30, max_value=120))
    steps = draw(st.lists(st.floats(-1, 1), min_size=n, max_size=n))
    spreads = draw(st.lists(st.floats(0.05, 1.5), min_size=n, max_size=n))
    price = 100.0
    bars = []
    for i, (step, spread) in enumerate(zip(steps, spreads, strict=True)):
        o = price
        c = price + step
        high = max(o, c) + spread
        low = min(o, c) - spread
        bars.append(bar(i, o, high, low, c))
        price = c
    return bars


@given(series(), st.integers(min_value=1, max_value=4))
@settings(max_examples=80, deadline=None)
def test_every_event_is_causal(bars: list[Bar], m: int) -> None:
    for event in run(bars, m):
        assert event.is_causal()
        assert event.state in {
            EventState.ACCEPTED,
            EventState.REJECTED,
            EventState.UNRESOLVED,
        }


@given(series(), st.integers(min_value=1, max_value=3), st.integers(min_value=10, max_value=29))
@settings(max_examples=80, deadline=None)
def test_truncation_gives_a_prefix_of_the_events(bars: list[Bar], m: int, cut: int) -> None:
    """Dropping the future cannot change what was decided before it (no repaint)."""
    full = [e for e in run(bars, m) if e.state is not EventState.UNRESOLVED]
    head = bars[:cut]
    horizon = head[-1].close_time
    short = [e for e in run(head, m) if e.state is not EventState.UNRESOLVED]
    expected = [e for e in full if e.decision_time <= horizon]
    assert short == expected


@given(series(), st.integers(min_value=1, max_value=3), st.integers(min_value=10, max_value=29))
@settings(max_examples=80, deadline=None)
def test_future_garbage_cannot_change_past_decisions(bars: list[Bar], m: int, cut: int) -> None:
    rng = np.random.default_rng(cut)
    garbage = []
    price = 100.0
    for i in range(cut, len(bars)):
        c = price + float(rng.normal(0, 40))
        garbage.append(bar(i, price, max(price, c) + 5, min(price, c) - 5, c))
        price = c
    mutated = [*bars[:cut], *garbage]
    horizon = bars[cut - 1].close_time
    a = [
        e
        for e in run(bars, m)
        if e.decision_time <= horizon and e.state is not EventState.UNRESOLVED
    ]
    b = [
        e
        for e in run(mutated, m)
        if e.decision_time <= horizon and e.state is not EventState.UNRESOLVED
    ]
    assert a == b


# -- primitives ----------------------------------------------------------------------------


def test_volatility_compression_uses_only_the_bars_given() -> None:
    wide = [bar(i, 5, 7, 3, 5) for i in range(20)]
    narrow = [bar(20 + i, 5, 5.2, 4.8, 5) for i in range(5)]
    assert volatility_compressed([*wide, *narrow], 5, 25, 0.5) is True
    assert volatility_compressed(wide, 5, 20, 0.5) is False
    assert volatility_compressed(wide[:5], 5, 20, 0.5) is None


def test_trend_context() -> None:
    assert trend_context([1, 2, 3, 4, 5], 5) == "UP"
    assert trend_context([5, 4, 3, 2, 1], 5) == "DOWN"
    assert trend_context([1, 2], 5) == "UNKNOWN"
    assert trend_context([2, 2, 2], 3) == "FLAT"
