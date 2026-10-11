"""The common contract for chart-pattern detectors, and the causality harness.

Detector quality and strategy quality are different things and the contract keeps them apart:

* a detection says "this geometry was found, and it was knowable at bar X";
* ``evidence`` is always ``GEOMETRY_ONLY`` and ``outcome_evidence`` is always ``NONE`` unless a
  separately authorised outcome study says otherwise. A detection is not a signal and is never a
  recommendation; ``reference_levels`` are labelled geometry (where the textbook draws a stop or a
  measured move), not orders.

Three bar indexes are kept apart on purpose (bars are 0-based positions in the input arrays):

* ``geometry_known_at``: the bar at which the last point of the geometry became confirmed;
* ``detected_at``: the bar at which the whole pattern, including its trigger event, is known;
* ``actionable_at``: the bar whose CLOSE is the earliest moment a person could act (so the first
  executable price is the next bar's open). For every detector so far it equals ``detected_at``.

``point.bar`` (where a point formed) is NOT when it was known (``point.confirmed_at``). Drawing a
label at ``point.bar`` on a chart at a time earlier than ``detected_at`` would be hidden hindsight.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable, Sequence
from typing import Literal

import numpy as np
from numpy.typing import ArrayLike
from pydantic import BaseModel, ConfigDict, Field, model_validator

PatternType = Literal[
    "WOLFE_WAVE",
    "DOUBLE_TOP",
    "DOUBLE_BOTTOM",
    "HEAD_AND_SHOULDERS",
    "INVERSE_HEAD_AND_SHOULDERS",
]


class PatternPoint(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    label: str  # "P1".."P5", "A", "V", "B", "LS", "HEAD", "RS", ...
    bar: int  # where the extreme formed
    price: float
    confirmed_at: int  # when it became knowable


class PatternDetection(BaseModel):
    """One detected geometry. Immutable, comparable, serialisable."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    pattern_id: str
    pattern_type: PatternType
    bias: Literal["LONG", "SHORT"]  # the direction the textbook pattern implies; not advice
    points: tuple[PatternPoint, ...]
    geometry_known_at: int
    detected_at: int
    actionable_at: int
    trigger_bar: int | None = None
    """Where the trigger event happened (a neckline break); None when the pattern has no trigger."""
    trigger_delay_bars: int = Field(default=0, ge=0)
    """``detected_at - trigger_bar``: how late the detection is versus the textbook trigger."""
    geometry_fit: float | None = Field(default=None, ge=0.0, le=1.0)
    """Fit to the *definition's* tolerances (1 = exact). It is not a probability of success."""
    source_definition: str
    reference_levels: dict[str, float] = Field(default_factory=dict)
    evidence: Literal["GEOMETRY_ONLY"] = "GEOMETRY_ONLY"
    outcome_evidence: Literal["NONE"] = "NONE"
    metadata: dict[str, float | int | str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _times_are_ordered(self) -> PatternDetection:
        if not (
            self.geometry_known_at <= self.detected_at <= self.actionable_at
            and all(p.confirmed_at <= self.geometry_known_at for p in self.points)
        ):
            msg = (
                "geometry_known_at <= detected_at <= actionable_at, and every point confirmed first"
            )
            raise ValueError(msg)
        return self


def make_pattern_id(pattern_type: str, points: Sequence[PatternPoint]) -> str:
    key = pattern_type + "|" + ",".join(f"{p.label}:{p.bar}:{p.price:.6f}" for p in points)
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:12]


Detector = Callable[[ArrayLike, ArrayLike, ArrayLike], list[PatternDetection]]


def causality_violations(
    detect: Detector,
    high: ArrayLike,
    low: ArrayLike,
    close: ArrayLike,
    cuts: Sequence[int],
) -> list[str]:
    """Prove a detector cannot see the future.

    For each cut ``t`` the detector is run on the data up to and including bar ``t`` only; its
    output must equal the detections of the full run whose ``actionable_at <= t``. Any difference
    means the detector used information that did not yet exist, or that a detection can change
    after the fact (repaint). Returns one message per violation (empty list = causal on these cuts).
    """
    h, lo, c = (np.asarray(x, dtype=np.float64) for x in (high, low, close))
    full = detect(h, lo, c)
    problems: list[str] = []
    for t in cuts:
        prefix = detect(h[: t + 1], lo[: t + 1], c[: t + 1])
        expected = [d for d in full if d.actionable_at <= t]
        if prefix != expected:
            got = {d.pattern_id for d in prefix}
            want = {d.pattern_id for d in expected}
            problems.append(
                f"cut {t}: prefix run gave {len(prefix)}, full run has {len(expected)} "
                f"(only in prefix: {sorted(got - want)[:3]}, "
                f"only in full: {sorted(want - got)[:3]})"
            )
    return problems
