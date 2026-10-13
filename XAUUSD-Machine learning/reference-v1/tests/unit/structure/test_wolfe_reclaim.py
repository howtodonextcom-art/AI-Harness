"""Wolfe with the confirmation variant: enter only after a close back inside line 1-3."""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
import pytest
from numpy.typing import ArrayLike

from xau_edge.structure.detection import PatternDetection, causality_violations
from xau_edge.structure.pivots import Pivot
from xau_edge.structure.wolfe import (
    WolfeConfig,
    _await_reclaim,
    _Lines,
    detect_wolfe,
    detect_wolfe_patterns,
)

pytestmark = pytest.mark.unit

Arrays = tuple[np.ndarray, np.ndarray, np.ndarray]  # type: ignore[type-arg,unused-ignore]
RECLAIM = WolfeConfig(entry_trigger="LINE13_RECLAIM")
# like the textbook path, but price lingers under line 1-3 after P5 before it climbs back
SLOW = [(0, 105.0), (10, 100.0), (30, 110.0), (50, 98.0), (70, 106.0), (90, 95.0),
        (105, 95.6), (140, 108.0)]  # fmt: skip


def path(points: Sequence[tuple[float, float]], pad: float = 0.1) -> Arrays:
    xs = [p[0] for p in points]
    close = np.interp(np.arange(xs[0], xs[-1] + 1), xs, [p[1] for p in points])
    return close + pad, close - pad, close


def test_reclaim_is_later_than_p5_confirmation_and_matches_an_independent_calculation() -> None:
    high, low, close = path(SLOW)
    default = detect_wolfe_patterns(high, low, close)
    late = detect_wolfe_patterns(high, low, close, RECLAIM)
    assert len(default) == len(late) == 1
    d, r = default[0], late[0]
    assert d.detected_at == d.geometry_known_at == 93  # P5 at bar 90, known 3 bars later
    assert r.geometry_known_at == 93 and r.detected_at > 93  # but the reclaim comes later
    # independent: line through the P1 and P3 lows, first close above it after P5
    p1, p3 = r.points[0], r.points[2]
    slope = (p3.price - p1.price) / (p3.bar - p1.bar)
    expected = next(k for k in range(91, len(close)) if close[k] > p1.price + slope * (k - p1.bar))
    assert r.trigger_bar == expected and r.detected_at == max(expected, 93)
    assert r.trigger_delay_bars == r.detected_at - r.trigger_bar
    assert r.reference_levels["entry_reference"] > d.reference_levels["entry_reference"]
    assert r.reference_levels["stop_reference"] == d.reference_levels["stop_reference"]  # still P5
    later = float(r.metadata["reward_risk_reference"])
    assert later < float(d.metadata["reward_risk_reference"])  # entering later costs R:R


def test_a_reclaim_already_made_during_confirmation_is_reported_at_confirmation() -> None:
    high, low, close = path(
        [(0, 105.0), (10, 100.0), (30, 110.0), (50, 98.0), (70, 106.0), (90, 95.0), (130, 108.0)]
    )
    only = detect_wolfe_patterns(high, low, close, RECLAIM)[0]
    assert (
        only.detected_at == only.geometry_known_at == 93
    )  # nothing earlier than P5's confirmation
    assert only.trigger_bar is not None and only.trigger_bar <= 93


def test_mirror_gives_the_same_timing_for_the_bearish_case() -> None:
    bull = detect_wolfe_patterns(*path(SLOW), RECLAIM)[0]
    bear_points = [(x, 200.0 - y) for x, y in SLOW]
    bear = detect_wolfe_patterns(*path(bear_points), RECLAIM)[0]
    assert bear.bias == "SHORT" and bull.bias == "LONG"
    assert (bear.detected_at, bear.trigger_bar) == (bull.detected_at, bull.trigger_bar)
    assert bear.reference_levels["stop_reference"] == pytest.approx(
        200 - bull.reference_levels["stop_reference"]
    )


def test_waiting_longer_than_allowed_drops_the_setup() -> None:
    high, low, close = path(SLOW)
    assert (
        detect_wolfe(
            high, low, close, WolfeConfig(entry_trigger="LINE13_RECLAIM", max_reclaim_bars=2)
        )
        == []
    )


def _five() -> list[Pivot]:
    return [
        Pivot(10, 100.0, "L", 13),
        Pivot(30, 110.0, "H", 33),
        Pivot(50, 98.0, "L", 53),
        Pivot(70, 106.0, "H", 73),
        Pivot(90, 94.0, "L", 93),
    ]


def test_a_low_through_p5_before_the_reclaim_kills_the_setup() -> None:
    lines = _Lines(s13=-0.05, b13=100.5, s14=0.1, b14=99.0)  # line 1-3 is about 96 at bar 90
    n = 130
    close = np.full(n, 94.5)
    low = np.full(n, 94.3)
    high = close + 0.2
    close[100:] = 99.0  # a reclaim at bar 100 ...
    assert _await_reclaim(
        _five(), lines, low, close, WolfeConfig(entry_trigger="LINE13_RECLAIM")
    ) == (100, 100)
    low[96] = 93.0  # ... but a wick pierces the P5 stop (94.0) first
    assert (
        _await_reclaim(_five(), lines, low, close, WolfeConfig(entry_trigger="LINE13_RECLAIM"))
        is None
    )
    assert high.shape == close.shape


def test_reclaim_mode_is_causal_on_random_walks() -> None:
    def detector(h: ArrayLike, lo: ArrayLike, c: ArrayLike) -> list[PatternDetection]:
        return detect_wolfe_patterns(h, lo, c, RECLAIM)

    produced = 0
    for seed in range(14):
        rng = np.random.default_rng(seed)
        close = 100 + np.cumsum(rng.normal(0, 0.3, 700))
        high = close + np.abs(rng.normal(0, 0.1, 700))
        low = close - np.abs(rng.normal(0, 0.1, 700))
        assert causality_violations(detector, high, low, close, range(40, 700, 11)) == []
        produced += len(detector(high, low, close))
    assert produced > 10  # the check saw real reclaim detections


def test_reclaim_delays_are_real_in_random_data_and_never_negative() -> None:
    """The trigger can precede the detection (it was made inside the confirmation window) but a
    detection is never before its geometry is known."""
    rng = np.random.default_rng(3)
    close = 100 + np.cumsum(rng.normal(0, 0.3, 700))
    high = close + np.abs(rng.normal(0, 0.1, 700))
    low = close - np.abs(rng.normal(0, 0.1, 700))
    full = detect_wolfe_patterns(high, low, close, RECLAIM)
    assert any(
        d.trigger_bar is not None and d.trigger_bar < d.detected_at for d in full
    )  # delay exists
    assert all(d.geometry_known_at <= d.detected_at for d in full)
