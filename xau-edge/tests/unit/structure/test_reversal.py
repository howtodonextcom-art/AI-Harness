"""Double top/bottom and head and shoulders, the detection contract and the causality harness.

Synthetic geometry only: no market data, no outcome, no performance claim.
"""

from __future__ import annotations

import collections
from collections.abc import Sequence
from typing import Any

import numpy as np
import pytest
from numpy.typing import ArrayLike
from pydantic import ValidationError

from xau_edge.structure.detection import (
    PatternDetection,
    PatternPoint,
    causality_violations,
    make_pattern_id,
)
from xau_edge.structure.pivots import Pivot, alternate, confirmed_pivots
from xau_edge.structure.reversal import ReversalConfig, detect_reversals, make_detector
from xau_edge.structure.wolfe import detect_wolfe_patterns

pytestmark = pytest.mark.unit

Arrays = tuple[np.ndarray, np.ndarray, np.ndarray]  # type: ignore[type-arg,unused-ignore]
# (bar, price) turning points: A peak, V valley, B peak (equal), then a fall through the valley
DOUBLE_TOP = [(0, 100.0), (20, 110.0), (40, 100.0), (60, 109.8), (80, 90.0), (100, 88.0)]
HNS = [
    (0, 100.0),
    (15, 106.0),
    (30, 101.0),
    (45, 112.0),
    (60, 100.5),
    (75, 106.2),
    (100, 90.0),
    (120, 88.0),
]


def path(points: Sequence[tuple[float, float]], pad: float = 0.1) -> Arrays:
    xs = [p[0] for p in points]
    close = np.interp(np.arange(xs[0], xs[-1] + 1), xs, [p[1] for p in points])
    return close + pad, close - pad, close


def mirror(points: Sequence[tuple[float, float]]) -> list[tuple[float, float]]:
    return [(x, 200.0 - y) for x, y in points]


def random_walk(seed: int, n: int = 800) -> Arrays:
    rng = np.random.default_rng(seed)
    close = 100 + np.cumsum(rng.normal(0, 0.3, n))
    return (
        close + np.abs(rng.normal(0, 0.1, n)),
        close - np.abs(rng.normal(0, 0.1, n)),
        close,
    )


def test_double_top_found_with_ordered_times_and_reference_levels() -> None:
    found = detect_reversals(*path(DOUBLE_TOP))
    assert [d.pattern_type for d in found] == ["DOUBLE_TOP"]
    top = found[0]
    assert top.bias == "SHORT" and [p.label for p in top.points] == ["A", "V", "B"]
    assert [p.bar for p in top.points] == [20, 40, 60]
    # B at bar 60 is only known 3 bars later; the neckline break comes later still
    assert top.geometry_known_at == 63 < top.detected_at == top.actionable_at
    assert all(p.confirmed_at <= top.geometry_known_at for p in top.points)
    assert top.reference_levels["invalidation_reference"] == pytest.approx(110.1)
    assert top.reference_levels["neckline_at_trigger"] == pytest.approx(99.9)
    assert top.reference_levels["trigger_close"] < 99.9  # the close that broke the neckline
    assert top.evidence == "GEOMETRY_ONLY" and top.outcome_evidence == "NONE"
    assert 0.0 <= (top.geometry_fit or 0.0) <= 1.0


def test_double_bottom_is_the_exact_mirror() -> None:
    top = detect_reversals(*path(DOUBLE_TOP))[0]
    bottom = detect_reversals(*path(mirror(DOUBLE_TOP)))[0]
    assert bottom.pattern_type == "DOUBLE_BOTTOM" and bottom.bias == "LONG"
    assert (bottom.geometry_known_at, bottom.detected_at) == (
        top.geometry_known_at,
        top.detected_at,
    )
    assert [p.bar for p in bottom.points] == [p.bar for p in top.points]
    assert bottom.points[0].price == pytest.approx(200 - top.points[0].price)
    assert (
        bottom.reference_levels["measured_move_reference"]
        > bottom.reference_levels["neckline_at_trigger"]
    )  # a bottom projects upwards


def test_head_and_shoulders_and_inverse() -> None:
    found = detect_reversals(*path(HNS))
    assert [d.pattern_type for d in found] == ["HEAD_AND_SHOULDERS"]
    hns = found[0]
    assert [p.label for p in hns.points] == ["LS", "V1", "HEAD", "V2", "RS"]
    assert hns.points[2].price > max(hns.points[0].price, hns.points[4].price)
    assert hns.geometry_known_at == 78 < hns.detected_at
    inverse = detect_reversals(*path(mirror(HNS)))
    assert [d.pattern_type for d in inverse] == ["INVERSE_HEAD_AND_SHOULDERS"]
    assert inverse[0].bias == "LONG" and inverse[0].detected_at == hns.detected_at


@pytest.mark.parametrize(
    "points",
    [
        [
            (0, 100.0),
            (20, 110.0),
            (40, 100.0),
            (60, 106.0),
            (80, 90.0),
            (100, 88.0),
        ],  # unequal peaks
        [(0, 100.0), (20, 110.0), (40, 100.0), (60, 109.8), (80, 105.0), (100, 104.0)],  # no break
        [(0, 100.0), (20, 110.0), (40, 100.0), (60, 109.8), (70, 113.5), (90, 90.0), (110, 88.0)],
    ],
    ids=["unequal-peaks", "neckline-never-broken", "peak-exceeded-first"],
)
def test_double_top_negative_cases(points: list[tuple[float, float]]) -> None:
    assert [d for d in detect_reversals(*path(points)) if d.pattern_type == "DOUBLE_TOP"] == []


def test_double_top_parameters_gate_the_pattern() -> None:
    data = path(DOUBLE_TOP)
    assert detect_reversals(*data, ReversalConfig(min_height_atr=60.0)) == []  # too small
    assert detect_reversals(*data, ReversalConfig(max_break_bars=3)) == []  # break came too late
    assert detect_reversals(*data, ReversalConfig(min_bars_between=30)) == []  # legs too short
    assert detect_reversals(*data, ReversalConfig(max_pattern_bars=20)) == []  # too wide
    assert detect_reversals(*data, kinds=("HNS",)) == []  # kinds switch works


def test_unequal_peaks_pass_only_with_a_wider_tolerance() -> None:
    unequal = [(0, 100.0), (20, 110.0), (40, 100.0), (60, 107.0), (80, 90.0), (100, 88.0)]
    data = path(unequal)
    assert detect_reversals(*data, ReversalConfig(equal_tolerance=0.25)) == []
    wide = detect_reversals(*data, ReversalConfig(equal_tolerance=0.45))
    assert [d.pattern_type for d in wide] == ["DOUBLE_TOP"]


def test_head_must_stand_above_both_shoulders() -> None:
    flat_head = [
        (0, 100.0),
        (15, 106.0),
        (30, 101.0),
        (45, 107.0),
        (60, 100.5),
        (75, 106.2),
        (100, 90.0),
    ]
    assert detect_reversals(*path(flat_head), kinds=("HNS",)) == []


def test_neckline_already_broken_at_confirmation_is_reported_late_not_hidden() -> None:
    fast = [(0, 100.0), (20, 110.0), (40, 100.0), (60, 109.8), (62, 95.0), (80, 90.0)]
    found = detect_reversals(*path(fast))
    assert len(found) == 1
    top = found[0]
    assert top.detected_at == top.geometry_known_at  # known only at confirmation
    assert top.trigger_delay_bars >= 1  # and the break was earlier: say so
    assert top.trigger_bar is not None and top.trigger_bar < top.detected_at


def test_a_superseded_peak_retires_the_pattern_built_on_it() -> None:
    # B is replaced by a higher peak before any break: the old (A, V, B) must not trigger later
    points = [
        (0, 100.0),
        (20, 110.0),
        (40, 100.0),
        (60, 109.8),
        (70, 109.9),
        (90, 90.0),
        (110, 88.0),
    ]
    found = detect_reversals(*path(points))
    ids = [d.pattern_id for d in found]
    assert len(ids) == len(set(ids))
    for d in found:
        assert d.points[-1].bar != 60  # the replaced peak is never the final point


def test_causality_on_random_walks_and_every_cut() -> None:
    detector = make_detector()
    produced = 0
    for seed in range(12):
        h, lo, c = random_walk(seed)
        assert causality_violations(detector, h, lo, c, range(40, len(c), 11)) == []
        produced += len(detector(h, lo, c))
    assert produced > 20  # the test saw real detections, so it is not vacuous


def test_the_causality_harness_catches_a_detector_that_peeks() -> None:
    h, lo, c = random_walk(3)
    full = make_detector()(h, lo, c)
    assert full

    # cheat: report each detection as soon as its LAST POINT FORMED, ignoring confirmation
    def cheating(high: ArrayLike, low: ArrayLike, close: ArrayLike) -> list[PatternDetection]:
        n = len(np.asarray(close))
        return [d for d in full if d.points[-1].bar < n]

    assert causality_violations(cheating, h, lo, c, range(40, len(c), 11))


def test_wolfe_through_the_common_contract_is_causal_too() -> None:
    def detector(h: ArrayLike, lo: ArrayLike, c: ArrayLike) -> list[PatternDetection]:
        return detect_wolfe_patterns(h, lo, c)

    for seed in range(6):
        h, lo, c = random_walk(seed, 600)
        assert causality_violations(detector, h, lo, c, range(40, len(c), 13)) == []
    bull = [(0, 105.0), (10, 100.0), (30, 110.0), (50, 98.0), (70, 106.0), (90, 95.0), (130, 108.0)]
    found = detect_wolfe_patterns(*path(bull))
    assert len(found) == 1 and found[0].pattern_type == "WOLFE_WAVE"
    assert found[0].geometry_known_at == found[0].detected_at == found[0].actionable_at == 93
    assert [p.label for p in found[0].points] == ["P1", "P2", "P3", "P4", "P5"]


def test_contract_rejects_disordered_times_and_is_immutable() -> None:
    def point(label: str, bar: int, confirmed: int) -> PatternPoint:
        return PatternPoint(label=label, bar=bar, price=1.0, confirmed_at=confirmed)

    common: dict[str, Any] = {
        "pattern_type": "DOUBLE_TOP", "bias": "SHORT", "source_definition": "x",
        "pattern_id": "x",
    }  # fmt: skip
    ok = PatternDetection(
        points=(point("A", 1, 4),),
        geometry_known_at=4,
        detected_at=6,
        actionable_at=6,
        **common,
    )
    with pytest.raises(ValidationError):  # detected before the geometry was known
        PatternDetection(
            points=(point("A", 1, 4),),
            geometry_known_at=4,
            detected_at=3,
            actionable_at=3,
            **common,
        )
    with pytest.raises(ValidationError):  # a point confirmed after the geometry was "known"
        PatternDetection(
            points=(point("A", 1, 9),),
            geometry_known_at=4,
            detected_at=6,
            actionable_at=6,
            **common,
        )
    with pytest.raises(ValidationError):
        ok.detected_at = 9  # type: ignore[misc]
    with pytest.raises(ValidationError):  # outcome evidence cannot be claimed by a detector
        PatternDetection(
            points=(point("A", 1, 4),),
            geometry_known_at=4,
            detected_at=6,
            actionable_at=6,
            outcome_evidence="POSITIVE",
            **common,
        )


def test_pattern_id_is_deterministic_and_geometry_sensitive() -> None:
    a = (PatternPoint(label="A", bar=1, price=2.0, confirmed_at=4),)
    b = (PatternPoint(label="A", bar=1, price=2.5, confirmed_at=4),)
    assert make_pattern_id("DOUBLE_TOP", a) == make_pattern_id("DOUBLE_TOP", a)
    assert make_pattern_id("DOUBLE_TOP", a) != make_pattern_id("DOUBLE_TOP", b)


def test_shared_pivots_apply_the_confirmation_rule_and_report_supersession() -> None:
    h, lo, c = path(DOUBLE_TOP)
    pivots = confirmed_pivots(h, lo, c, left=3, right=3)
    assert pivots and all(p.confirmed_at == p.bar + 3 for p in pivots)
    history: list[Pivot] = []
    assert alternate(history, Pivot(10, 5.0, "H", 13)) is None
    assert alternate(history, Pivot(20, 4.0, "H", 23)) is None  # weaker same-kind: ignored
    old = alternate(history, Pivot(30, 6.0, "H", 33))  # stronger same-kind: replaces
    assert old == Pivot(10, 5.0, "H", 13) and history[-1].bar == 30


def test_flat_series_and_empty_input_produce_nothing() -> None:
    flat = np.full(300, 100.0)
    assert detect_reversals(flat + 0.1, flat - 0.1, flat) == []
    assert detect_reversals(np.array([]), np.array([]), np.array([])) == []


def test_one_neckline_break_is_reported_once_even_when_a_peak_is_superseded() -> None:
    """Regression: a pattern on a peak that a higher peak replaced at the SAME bar used to fire
    together with the pattern on the new peak (3 duplicates in 150 random walks, 0 now)."""
    seen = collections.Counter[tuple[int, str, int, int, int]]()
    for seed in range(60):
        h, lo, c = random_walk(seed, 3000)
        for d in detect_reversals(h, lo, c):
            if d.pattern_type in ("DOUBLE_TOP", "DOUBLE_BOTTOM"):
                seen[(seed, d.pattern_type, d.points[0].bar, d.points[1].bar, d.detected_at)] += 1
    assert sum(seen.values()) > 100  # the check saw many detections
    assert [k for k, v in seen.items() if v > 1] == []
