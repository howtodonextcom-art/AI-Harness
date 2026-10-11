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

    Entry is the trigger close (neckline break) or the entry reference (Wolfe); risk runs to the
    invalidation reference (the peak, or P5); reward runs to the measured-move or EPA reference.
    This is where the picture itself puts the levels, before costs. It is a property of the shape at
    the moment of detection and says nothing about what price does afterwards.
    """
    ref = detection.reference_levels
    entry = ref.get("trigger_close", ref.get("entry_reference"))
    stop = ref.get("invalidation_reference", ref.get("stop_reference"))
    target = ref.get("measured_move_reference", ref.get("target_reference"))
    if entry is None or stop is None or target is None:
        return None
    risk, reward = abs(entry - stop), abs(target - entry)
    if risk <= 0:
        return None
    return reward / risk


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
    out["distinct_pattern_ids"] = len({d.pattern_id for d in detections})
    out["overlap"] = overlap_stats(detections)
    if timestamps is not None:
        by_year = Counter(timestamps[d.actionable_at].year for d in detections)
        by_hour = Counter(timestamps[d.actionable_at].hour for d in detections)
        out["per_year"] = {str(k): v for k, v in sorted(by_year.items())}
        out["by_actionable_hour_utc"] = {str(k): v for k, v in sorted(by_hour.items())}
    return out
