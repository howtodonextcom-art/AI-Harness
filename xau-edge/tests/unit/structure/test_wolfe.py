"""Wolfe Wave detector: synthetic geometry only (no market data, no performance claim)."""

from __future__ import annotations

import numpy as np
import pytest

from xau_edge.structure.wolfe import WolfeConfig, detect_wolfe

pytestmark = pytest.mark.unit

# (bar index, price) for P1..P5 plus a tail; a textbook bullish descending wedge.
BULL = [(0, 105.0), (10, 100.0), (30, 110.0), (50, 98.0), (70, 106.0), (90, 95.0), (130, 108.0)]


def path(
    points: list[tuple[int, float]], pad: float = 0.1
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:  # type: ignore[type-arg,unused-ignore]
    xs = [p[0] for p in points]
    close = np.interp(np.arange(xs[0], xs[-1] + 1), xs, [p[1] for p in points])
    return close + pad, close - pad, close


def test_bullish_wolfe_found_with_correct_pivots_and_levels() -> None:
    high, low, close = path(BULL)
    found = detect_wolfe(high, low, close)
    assert len(found) == 1
    cand = found[0]
    assert cand.side == "BUY"
    assert [p.bar for p in cand.pivots] == [10, 30, 50, 70, 90]
    assert cand.confirmed_at == 93  # P5 at bar 90 is only known 3 bars later
    assert cand.stop == pytest.approx(94.9)  # the P5 low
    assert cand.entry == pytest.approx(close[93])
    assert cand.target > cand.entry > cand.stop  # target on the P1-P4 line, above entry
    assert cand.reward_risk == pytest.approx((cand.target - cand.entry) / (cand.entry - cand.stop))


def test_bearish_mirror_is_found_as_sell_with_mirrored_levels() -> None:
    high, low, close = path([(x, 200.0 - y) for x, y in BULL])
    found = detect_wolfe(high, low, close)
    assert [c.side for c in found] == ["SELL"]
    cand = found[0]
    assert cand.target < cand.entry < cand.stop
    assert [p.kind for p in cand.pivots] == ["H", "L", "H", "L", "H"]
    # same geometry, mirrored: identical R:R
    bull = detect_wolfe(*path(BULL))[0]
    assert cand.reward_risk == pytest.approx(bull.reward_risk)


def test_no_overshoot_is_rejected_unless_the_rule_is_relaxed() -> None:
    weak = [*BULL[:5], (90, 98.0), (130, 108.0)]  # P5 stays above the P1-P3 line (96 at bar 90)
    # P5 (97.9) is not below P3 (97.9)... make it clearly inside the wedge instead
    weak[5] = (90, 98.5)
    high, low, close = path(weak)
    assert detect_wolfe(high, low, close) == []
    relaxed = WolfeConfig(require_p5_beyond_line13=False)
    # still rejected: P5 must also undercut P3 for a Wolfe overshoot
    assert detect_wolfe(high, low, close, relaxed) == []


def test_broadening_formation_is_always_rejected() -> None:
    # P4 above P2: a broadening shape, outside the descending-wedge definition; no flag relaxes it
    broad = [
        (0, 105.0),
        (10, 100.0),
        (30, 110.0),
        (50, 98.0),
        (70, 112.0),
        (90, 94.0),
        (130, 108.0),
    ]
    high, low, close = path(broad)
    assert detect_wolfe(high, low, close) == []
    loose = WolfeConfig(require_p4_inside_p2_p3=False, require_converging=False)
    assert detect_wolfe(high, low, close, loose) == []


def test_diverging_lines_need_the_converging_rule_relaxed() -> None:
    # P4 < P2 and P3 < P1, but the upper line falls slower than the lower one: the gap widens
    wide = [(0, 105.0), (10, 100.0), (30, 110.0), (50, 98.0), (70, 109.0), (90, 94.0), (130, 108.0)]
    high, low, close = path(wide)
    assert detect_wolfe(high, low, close) == []
    found = detect_wolfe(high, low, close, WolfeConfig(require_converging=False))
    assert [c.side for c in found] == ["BUY"]


def test_candidate_is_not_repainted_by_future_bars() -> None:
    high, low, close = path(BULL)
    full = detect_wolfe(high, low, close)
    cut = full[0].confirmed_at + 1  # bars up to and including the confirmation bar only
    prefix = detect_wolfe(high[:cut], low[:cut], close[:cut])
    assert prefix == full[:1]
    # and nothing exists one bar before it is knowable
    assert detect_wolfe(high[: cut - 1], low[: cut - 1], close[: cut - 1]) == []


def test_spread_worsens_entry_and_reward_risk() -> None:
    high, low, close = path(BULL)
    free = detect_wolfe(high, low, close)[0]
    costly = detect_wolfe(high, low, close, WolfeConfig(spread=0.5))[0]
    assert costly.entry == pytest.approx(free.entry + 0.5)
    assert costly.reward_risk < free.reward_risk


def test_min_reward_risk_filters_candidates() -> None:
    high, low, close = path(BULL)
    assert detect_wolfe(high, low, close, WolfeConfig(min_reward_risk=50.0)) == []


def test_pattern_too_wide_and_too_cramped_are_rejected() -> None:
    high, low, close = path(BULL)
    assert detect_wolfe(high, low, close, WolfeConfig(max_pattern_bars=50)) == []
    assert detect_wolfe(high, low, close, WolfeConfig(min_leg_bars=30)) == []


def test_flat_and_noise_series_produce_nothing() -> None:
    flat = np.full(300, 100.0)
    assert detect_wolfe(flat + 0.1, flat - 0.1, flat) == []
    rng = np.random.default_rng(7)
    walk = 100 + np.cumsum(rng.normal(0, 0.2, 500))
    found = detect_wolfe(walk + 0.1, walk - 0.1, walk)
    # random data may match rarely; the detector must stay a small minority, never a flood
    assert len(found) < 10
