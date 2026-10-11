"""Descriptive statistics of pattern detections: frequency, geometry, timing, overlap.

This module takes detections (and optionally bar timestamps) and NOTHING ELSE. It receives no price
array, so it is structurally unable to compute returns, win rates, target hits or any outcome: the
function signatures are the guarantee, and a test pins them. Anything outcome-dependent needs a
separate, explicitly authorised research charter.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from datetime import datetime
from statistics import median

from xau_edge.structure.detection import PatternDetection
from xau_edge.structure.formation import FormationState, FormationTrack


def _quantiles(values: Sequence[float]) -> dict[str, float] | None:
    if not values:
        return None
    ordered = sorted(values)

    def q(p: float) -> float:
        return ordered[min(len(ordered) - 1, round(p * (len(ordered) - 1)))]

    return {
        "min": ordered[0],
        "p25": q(0.25),
        "median": float(median(ordered)),
        "p75": q(0.75),
        "max": ordered[-1],
    }


def reference_reward_risk(detection: PatternDetection) -> float | None:
    """Gross reward-to-risk of the textbook geometry, from the detection's own reference levels.

    Entry is the actionable-close reference (or Wolfe entry reference); the earlier trigger close
    is retained as event context and must not be used as a fill. Risk runs to the invalidation
    reference (the peak, or P5); reward runs to the measured-move or EPA reference.
    This is where the picture itself puts the levels, before costs. It is a property of the shape at
    the moment of detection and says nothing about what price does afterwards.
    """
    ref = detection.reference_levels
    entry = ref.get("entry_reference", ref.get("trigger_close"))
    stop = ref.get("invalidation_reference", ref.get("stop_reference"))
    target = ref.get("measured_move_reference", ref.get("target_reference"))
    if entry is None or stop is None or target is None:
        return None
    risk, reward = abs(entry - stop), abs(target - entry)
    if risk <= 0:
        return None
    return reward / risk


def distance_to_invalidation_atr(detection: PatternDetection) -> float | None:
    """How far the textbook invalidation level is from the trigger close, in ATR (geometry only)."""
    ref = detection.reference_levels
    height = detection.metadata.get("height")
    height_atr = detection.metadata.get("height_atr")
    entry = ref.get("entry_reference", ref.get("trigger_close"))
    if entry is None or "invalidation_reference" not in ref:
        return None
    if not isinstance(height, float) or not isinstance(height_atr, float) or height_atr <= 0:
        return None
    return abs(ref["invalidation_reference"] - entry) / (height / height_atr)


def describe_formations(tracks: Sequence[FormationTrack], n_bars: int) -> dict[str, object]:
    """How structures progress: reach rates per milestone, why they fail, how long each step takes.

    A reach rate is a frequency of *structure*, not of price outcomes. It says how often a possible
    double top went on to be confirmed, never what price did after the confirmation.
    """
    n = len(tracks)
    out: dict[str, object] = {
        "structures": n,
        "per_10k_bars": 10_000 * n / n_bars if n_bars else 0.0,
    }
    states = Counter(t.state.value for t in tracks)
    out["final_state"] = dict(states)
    reached: dict[str, int] = {}
    for state in (
        FormationState.POSSIBLE,
        FormationState.DEVELOPING,
        FormationState.NEAR_CONFIRMATION,
        FormationState.CONFIRMED,
    ):
        reached[state.value] = sum(1 for t in tracks if any(e.state is state for e in t.events))
    out["reached"] = reached
    out["reached_share"] = {k: (v / n if n else 0.0) for k, v in reached.items()}
    out["invalidation_reasons"] = dict(
        Counter(t.invalidation_reason for t in tracks if t.invalidation_reason is not None)
    )
    confirmed = [t for t in tracks if t.state is FormationState.CONFIRMED]
    out["bars_start_to_confirmed"] = _quantiles(
        [t.confirmed_at - t.started_at for t in confirmed if t.confirmed_at is not None]
    )
    out["bars_start_to_invalidated"] = _quantiles(
        [t.invalidated_at - t.started_at for t in tracks if t.invalidated_at is not None]
    )
    near_to_confirmed = []
    for t in confirmed:
        near = next((e.bar for e in t.events if e.state is FormationState.NEAR_CONFIRMATION), None)
        if near is not None and t.confirmed_at is not None:
            near_to_confirmed.append(t.confirmed_at - near)
    out["bars_near_to_confirmed"] = _quantiles(near_to_confirmed)
    out["note"] = "structure frequencies only; no price outcome after confirmation is measured"
    return out


def overlap_stats(detections: Sequence[PatternDetection]) -> dict[str, float | int]:
    """Intervals run from the first point's bar to ``actionable_at``. Counts are over all pairs of
    consecutive detections ordered by start: ``overlapping`` shares any bar, ``nested`` is fully
    inside the previous one."""
    spans = sorted((d.points[0].bar, d.actionable_at) for d in detections)
    overlapping = nested = 0
    furthest_end = -1
    for start, end in spans:
        if start <= furthest_end:
            overlapping += 1
            if end <= furthest_end:
                nested += 1
        furthest_end = max(furthest_end, end)
    n = len(spans)
    return {
        "detections": n,
        "overlapping": overlapping,
        "nested": nested,
        "overlap_rate": overlapping / n if n else 0.0,
    }


def describe(
    detections: Sequence[PatternDetection],
    n_bars: int,
    timestamps: Sequence[datetime] | None = None,
) -> dict[str, object]:
    """Frequency, geometry and timing of ``detections`` found in ``n_bars`` bars."""
    out: dict[str, object] = {"n_bars": n_bars, "detections": len(detections)}
    out["per_10k_bars"] = 10_000 * len(detections) / n_bars if n_bars else 0.0
    out["by_type"] = dict(Counter(d.pattern_type for d in detections))
    out["by_bias"] = dict(Counter(d.bias for d in detections))
    # time that passes between a point forming and anyone being able to know it
    out["confirmation_lag_bars"] = _quantiles(
        [d.geometry_known_at - d.points[-1].bar for d in detections]
    )
    out["wait_for_trigger_bars"] = _quantiles(
        [d.detected_at - d.geometry_known_at for d in detections]
    )
    out["trigger_delay_bars"] = _quantiles([d.trigger_delay_bars for d in detections])
    out["duration_bars_first_point_to_actionable"] = _quantiles(
        [d.actionable_at - d.points[0].bar for d in detections]
    )
    out["leg_bars"] = _quantiles(
        [b.bar - a.bar for d in detections for a, b in zip(d.points, d.points[1:], strict=False)]
    )
    heights = [float(d.metadata["height_atr"]) for d in detections if "height_atr" in d.metadata]
    out["height_in_atr"] = _quantiles(heights)
    out["geometry_fit"] = _quantiles(
        [d.geometry_fit for d in detections if d.geometry_fit is not None]
    )
    rr = [r for d in detections if (r := reference_reward_risk(d)) is not None]
    out["reference_reward_risk_gross"] = _quantiles(rr)
    out["share_reference_rr_at_least_1_5"] = (
        sum(1 for r in rr if r >= 1.5) / len(rr) if rr else None
    )
    dist = [d for x in detections if (d := distance_to_invalidation_atr(x)) is not None]
    out["distance_to_invalidation_atr"] = _quantiles(dist)
    out["distinct_pattern_ids"] = len({d.pattern_id for d in detections})
    out["overlap"] = overlap_stats(detections)
    if timestamps is not None:
        by_year = Counter(timestamps[d.actionable_at].year for d in detections)
        by_hour = Counter(timestamps[d.actionable_at].hour for d in detections)
        out["per_year"] = {str(k): v for k, v in sorted(by_year.items())}
        out["by_actionable_hour_utc"] = {str(k): v for k, v in sorted(by_hour.items())}
    return out
