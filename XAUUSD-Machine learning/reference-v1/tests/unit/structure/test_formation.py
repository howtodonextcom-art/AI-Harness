"""Formation lifecycle of double tops/bottoms: states, progress, causality and parity."""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
import pytest

from xau_edge.structure.formation import (
    PROGRESS,
    FormationState,
    FormationTrack,
    lifecycle_violations,
    track_double_formations,
)
from xau_edge.structure.reversal import detect_reversals

pytestmark = pytest.mark.unit

Arrays = tuple[np.ndarray, np.ndarray, np.ndarray]  # type: ignore[type-arg,unused-ignore]
DOUBLE_TOP = [(0, 100.0), (20, 110.0), (40, 100.0), (60, 109.8), (80, 90.0), (100, 88.0)]


def path(points: Sequence[tuple[float, float]], pad: float = 0.1) -> Arrays:
    xs = [p[0] for p in points]
    close = np.interp(np.arange(xs[0], xs[-1] + 1), xs, [p[1] for p in points])
    return close + pad, close - pad, close


def walk(seed: int, n: int = 3000) -> Arrays:
    rng = np.random.default_rng(seed)
    close = 100 + np.cumsum(rng.normal(0, 0.3, n))
    return close + np.abs(rng.normal(0, 0.1, n)), close - np.abs(rng.normal(0, 0.1, n)), close


def track_from(tracks: list[FormationTrack], a_bar: int) -> FormationTrack:
    return next(t for t in tracks if t.points[0].bar == a_bar and t.pattern_type == "DOUBLE_TOP")


def test_a_clean_double_top_walks_through_every_state_with_milestone_progress() -> None:
    track = track_from(track_double_formations(*path(DOUBLE_TOP)), 20)
    steps = [(e.bar, e.state, e.formation_progress) for e in track.events]
    assert [s for _, s, _ in steps] == [
        FormationState.POSSIBLE, FormationState.DEVELOPING,
        FormationState.NEAR_CONFIRMATION, FormationState.CONFIRMED,
    ]  # fmt: skip
    assert [p for _, _, p in steps] == [25, 50, 75, 100]
    bars = [b for b, _, _ in steps]
    assert bars == sorted(bars) and bars[2] == 63  # B at bar 60 is only known at 63
    assert track.confirmed_at == track.actionable_at == 71 == bars[3]
    assert track.formation_progress == 100 and track.invalidated_at is None
    assert "not a win probability" in track.progress_note
    # the same structure through the detector
    detection = detect_reversals(*path(DOUBLE_TOP), kinds=("DOUBLE",))[0]
    assert detection.detected_at == track.confirmed_at
    assert track.detection_id == detection.pattern_id


def test_the_mirror_is_a_double_bottom_with_the_same_milestones() -> None:
    mirrored = [(x, 200.0 - y) for x, y in DOUBLE_TOP]
    tracks = track_double_formations(*path(mirrored))
    bottom = next(t for t in tracks if t.pattern_type == "DOUBLE_BOTTOM" and t.points[0].bar == 20)
    assert bottom.bias == "LONG" and bottom.confirmed_at == 71
    assert [e.formation_progress for e in bottom.events] == [25, 50, 75, 100]


def test_progress_values_are_only_the_five_milestones_and_never_go_back() -> None:
    allowed = {0, 25, 50, 75, 100}
    for seed in range(8):
        for t in track_double_formations(*walk(seed)):
            progress = [e.formation_progress for e in t.events]
            assert set(progress) <= allowed
            assert progress == sorted(progress)
            assert set(PROGRESS.values()) == {25, 50, 75, 100}


@pytest.mark.parametrize(
    ("points", "reason"),
    [
        (
            [(0, 100.0), (20, 110.0), (40, 100.0), (50, 116.0), (70, 100.0), (90, 99.0)],
            "PEAK_BAND_EXCEEDED",
        ),
        (
            [(0, 100.0), (20, 110.0), (40, 100.0), (50, 106.0), (58, 97.0), (80, 96.0)],
            "NECKLINE_BROKEN_FIRST",
        ),
        (
            [(0, 100.0), (20, 110.0), (40, 100.0), (50, 106.0), (60, 103.0), (80, 104.0)],
            "SECOND_PEAK_NOT_EQUAL",
        ),
    ],
    ids=["peak-exceeded", "neckline-broken-first", "second-peak-not-equal"],
)
def test_structures_that_fail_first_are_invalidated_with_a_reason(
    points: list[tuple[float, float]], reason: str
) -> None:
    track = track_from(track_double_formations(*path(points)), 20)
    assert track.state is FormationState.INVALIDATED and track.invalidation_reason == reason
    assert track.confirmed_at is None and track.invalidated_at is not None
    assert (
        track.formation_progress < 100
    )  # the last milestone it reached is kept, it never completed


def test_a_confirmed_structure_is_never_invalidated_later() -> None:
    track = track_from(track_double_formations(*path(DOUBLE_TOP)), 20)
    assert track.invalidated_at is None
    assert all(e.state is not FormationState.INVALIDATED for e in track.events)


def test_parity_with_the_detector_on_random_walks() -> None:
    compared = 0
    for seed in range(12):
        h, lo, c = walk(seed)
        confirmed = {
            (t.pattern_type, tuple(p.bar for p in t.points), t.confirmed_at)
            for t in track_double_formations(h, lo, c)
            if t.state is FormationState.CONFIRMED
        }
        detected = {
            (d.pattern_type, tuple(p.bar for p in d.points), d.detected_at)
            for d in detect_reversals(h, lo, c, kinds=("DOUBLE",))
        }
        assert confirmed == detected  # 0 unexplained differences
        compared += len(detected)
    assert compared > 100


def test_a_structure_that_only_qualifies_at_the_second_peak_starts_there() -> None:
    late = 0
    for seed in range(12):
        for t in track_double_formations(*walk(seed)):
            if (
                t.state is FormationState.CONFIRMED
                and t.events[0].state is FormationState.NEAR_CONFIRMATION
            ):
                late += 1
                # no earlier state is invented: it starts after the valley was known, and not
                # after the last second peak (a replaced earlier peak may have armed it first)
                assert t.points[1].confirmed_at < t.events[0].bar <= t.points[2].confirmed_at
    assert late > 0


def test_lifecycle_is_prefix_invariant_at_every_cut() -> None:
    for seed in range(6):
        h, lo, c = walk(seed, 900)
        assert lifecycle_violations(h, lo, c, list(range(40, 900, 17))) == []


def test_ids_are_stable_while_a_structure_grows() -> None:
    h, lo, c = walk(2, 900)
    full = {t.pattern_id: t for t in track_double_formations(h, lo, c)}
    stable = 0
    for cut in range(100, 900, 50):
        for t in track_double_formations(h[:cut], lo[:cut], c[:cut]):
            if t.pattern_id in full:
                stable += 1
                assert full[t.pattern_id].started_at == t.started_at
    assert stable > 10
