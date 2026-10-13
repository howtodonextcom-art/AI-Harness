"""Double top / double bottom and head and shoulders (and the inverse): neckline-break detectors.

Research tools, not signal sources. Rules are the common textbook geometry; where sources differ the
choice is a named parameter, and nothing here claims the patterns have predictive value.

Double top (bearish reversal; the double bottom is the exact mirror, found by negating prices):

* three alternating confirmed pivots: peak A, valley V, peak B;
* equal peaks: ``|B - A| <= equal_tolerance * height`` where ``height = max(A, B) - V``;
* the pattern is big enough: ``height >= min_height_atr * ATR(14)``;
* spacing and span: each leg at least ``min_bars_between``, A to B at most ``max_pattern_bars``;
* no bar between A and B above the higher peak;
* TRIGGER: the first CLOSE below the valley after B (the neckline break);
* the pattern dies if a close exceeds the higher peak first, or if no break happens within
  ``max_break_bars`` after the geometry became known.

Head and shoulders (bearish): peaks LS, HEAD, RS with valleys V1, V2 between them; the head must
exceed both shoulders by at least ``equal_tolerance * height``; shoulders equal within the same
tolerance; ``height = HEAD - mean(V1, V2)``; the neckline is the line through V1 and V2;
TRIGGER: the first close below the neckline after RS; it dies if a close exceeds the head first.

Causality is structural: the loop walks the bars once, in order. A pivot is used only at its
``confirmed_at`` bar, a candidate waits "armed" until a later bar's close triggers it, and a
detection is emitted at the bar that triggers it (``detected_at == actionable_at``). If the neckline
was already broken between the last peak and its confirmation, the detection is emitted at the
confirmation bar and ``metadata['trigger_delay_bars']`` says how late that is.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from itertools import pairwise
from typing import Literal

import numpy as np
from numpy.typing import ArrayLike
from pydantic import BaseModel, ConfigDict, Field

from xau_edge.features.indicators import as_hlc, atr
from xau_edge.structure.detection import (
    PatternDetection,
    PatternPoint,
    PatternType,
    make_pattern_id,
)
from xau_edge.structure.pivots import Pivot, alternate, confirmed_pivots

ATR_PERIOD = 14
DOUBLE_DEFINITION = "double-top-bottom/textbook-v1 (equal peaks, close beyond the valley)"
HNS_DEFINITION = "head-and-shoulders/textbook-v1 (head above both shoulders, close beyond neckline)"
Kind = Literal["DOUBLE", "HNS"]


class ReversalConfig(BaseModel):
    """Seven free parameters, all in one place (the ATR period is a fixed constant)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    pivot_left: int = Field(default=3, ge=1)
    pivot_right: int = Field(default=3, ge=1)
    equal_tolerance: float = Field(default=0.25, gt=0.0, le=1.0)
    min_height_atr: float = Field(default=2.0, ge=0.0)
    min_bars_between: int = Field(default=5, ge=1)
    max_pattern_bars: int = Field(default=200, ge=10)
    max_break_bars: int = Field(default=20, ge=1)


@dataclass
class _Armed:
    """Geometry that is known and waits for its trigger."""

    kind: Kind
    pivots: tuple[Pivot, ...]
    geometry_known_at: int
    expires_at: int
    peak: float  # a close above this kills the pattern
    neck_start: Pivot  # the neckline passes through these two points
    neck_end: Pivot
    height: float
    fit: float
    atr: float = 0.0

    def neckline(self, bar: int) -> float:
        slope = (self.neck_end.price - self.neck_start.price) / (
            self.neck_end.bar - self.neck_start.bar
        )
        return self.neck_start.price + slope * (bar - self.neck_start.bar)


def _spaced(pivots: tuple[Pivot, ...], cfg: ReversalConfig) -> bool:
    gaps_ok = all(b.bar - a.bar >= cfg.min_bars_between for a, b in pairwise(pivots))
    return gaps_ok and pivots[-1].bar - pivots[0].bar <= cfg.max_pattern_bars


def _arm_double(
    history: list[Pivot],
    j: int,
    high: np.ndarray,
    atr_j: float,
    cfg: ReversalConfig,  # type: ignore[type-arg,unused-ignore]
) -> _Armed | None:
    if len(history) < 3:
        return None
    a, v, b = history[-3:]
    if not _spaced((a, v, b), cfg):
        return None
    peak = max(a.price, b.price)
    height = peak - v.price
    if height <= 0 or height < cfg.min_height_atr * atr_j:
        return None
    gap = abs(b.price - a.price)
    if gap > cfg.equal_tolerance * height:
        return None
    if float(high[a.bar : b.bar + 1].max()) > peak:
        return None
    flat_end = Pivot(v.bar + 1, v.price, "L", v.confirmed_at + 1)  # a horizontal neckline
    fit = 1.0 - gap / (cfg.equal_tolerance * height)
    return _Armed(
        "DOUBLE", (a, v, b), j, j + cfg.max_break_bars, peak, v, flat_end, height, fit, atr_j
    )


def _arm_hns(
    history: list[Pivot],
    j: int,
    high: np.ndarray,
    atr_j: float,
    cfg: ReversalConfig,  # type: ignore[type-arg,unused-ignore]
) -> _Armed | None:
    if len(history) < 5:
        return None
    ls, v1, head, v2, rs = history[-5:]
    if not _spaced((ls, v1, head, v2, rs), cfg):
        return None
    height = head.price - (v1.price + v2.price) / 2
    if height <= 0 or height < cfg.min_height_atr * atr_j:
        return None
    tol = cfg.equal_tolerance * height
    if head.price - max(ls.price, rs.price) < tol or abs(rs.price - ls.price) > tol:
        return None
    if float(high[ls.bar : rs.bar + 1].max()) > head.price:
        return None
    fit = 1.0 - abs(rs.price - ls.price) / tol
    return _Armed(
        "HNS",
        (ls, v1, head, v2, rs),
        j,
        j + cfg.max_break_bars,
        head.price,
        v1,
        v2,
        height,
        fit,
        atr_j,
    )


def _scan_tops(
    h: np.ndarray,
    lo: np.ndarray,
    c: np.ndarray,
    atr_arr: np.ndarray,
    *,
    cfg: ReversalConfig,
    kinds: tuple[Kind, ...],  # type: ignore[type-arg,unused-ignore]
) -> list[tuple[_Armed, int, int]]:
    """Walk the bars once. Returns ``(pattern, trigger_bar, detected_at)`` for the top patterns."""
    pivots = confirmed_pivots(h, lo, c, left=cfg.pivot_left, right=cfg.pivot_right)
    history: list[Pivot] = []
    armed: list[_Armed] = []
    out: list[tuple[_Armed, int, int]] = []
    pi = 0
    for j in range(c.size):
        # 1. pivots that become known at j: retire what a superseded pivot built, arm new geometry
        fresh_now: list[_Armed] = []
        while pi < len(pivots) and pivots[pi].confirmed_at == j:
            pivot = pivots[pi]
            pi += 1
            replaced = alternate(history, pivot)
            if replaced is not None:  # whatever was built on the superseded pivot is retired
                armed = [p for p in armed if replaced not in p.pivots]
                fresh_now = [p for p in fresh_now if replaced not in p.pivots]
            if pivot.kind != "H" or history[-1] is not pivot or np.isnan(atr_arr[j]):
                continue
            for kind, arm in (("DOUBLE", _arm_double), ("HNS", _arm_hns)):
                if kind not in kinds:
                    continue
                fresh = arm(history, j, h, float(atr_arr[j]), cfg)
                if fresh is None:
                    continue
                verdict = _initial_scan(fresh, c, fresh.pivots[-1].bar + 1, j)
                if verdict is None:
                    fresh_now.append(fresh)
                elif verdict >= 0:
                    out.append((fresh, verdict, j))
        # 2. bar j for the patterns that were already waiting (closes only, after step 1 so that a
        #    pattern retired at j cannot also fire at j)
        survivors: list[_Armed] = []
        for pat in armed:
            if j > pat.expires_at or c[j] > pat.peak:
                continue
            if c[j] < pat.neckline(j):
                out.append((pat, j, j))
                continue
            survivors.append(pat)
        armed = survivors + fresh_now
    return out


def _initial_scan(pat: _Armed, c: np.ndarray, start: int, end: int) -> int | None:  # type: ignore[type-arg,unused-ignore]
    """Closes between the last peak and its confirmation: -1 dead, k >= 0 already triggered at k."""
    for k in range(start, end + 1):
        if c[k] > pat.peak:
            return -1
        if c[k] < pat.neckline(k):
            return k
    return None


_NAMES: dict[tuple[Kind, bool], PatternType] = {
    ("DOUBLE", False): "DOUBLE_TOP",
    ("DOUBLE", True): "DOUBLE_BOTTOM",
    ("HNS", False): "HEAD_AND_SHOULDERS",
    ("HNS", True): "INVERSE_HEAD_AND_SHOULDERS",
}
_LABELS: dict[Kind, tuple[str, ...]] = {
    "DOUBLE": ("A", "V", "B"),
    "HNS": ("LS", "V1", "HEAD", "V2", "RS"),
}


def _to_detection(
    pat: _Armed,
    *,
    trigger_bar: int,
    detected_at: int,
    close: np.ndarray,
    mirrored: bool,  # type: ignore[type-arg,unused-ignore]
) -> PatternDetection:
    sign = -1.0 if mirrored else 1.0
    points = tuple(
        PatternPoint(label=label, bar=p.bar, price=sign * p.price, confirmed_at=p.confirmed_at)
        for label, p in zip(_LABELS[pat.kind], pat.pivots, strict=True)
    )
    ptype = _NAMES[(pat.kind, mirrored)]
    neck = pat.neckline(trigger_bar)
    return PatternDetection(
        pattern_id=make_pattern_id(ptype, points),
        pattern_type=ptype,
        bias="LONG" if mirrored else "SHORT",
        points=points,
        geometry_known_at=pat.geometry_known_at,
        detected_at=detected_at,
        actionable_at=detected_at,
        trigger_bar=trigger_bar,
        trigger_delay_bars=detected_at - trigger_bar,
        geometry_fit=max(0.0, min(1.0, pat.fit)),
        source_definition=DOUBLE_DEFINITION if pat.kind == "DOUBLE" else HNS_DEFINITION,
        reference_levels={
            "neckline_at_trigger": sign * neck,
            "invalidation_reference": sign * pat.peak,
            "measured_move_reference": sign * (neck - pat.height),
            "trigger_close": float(close[trigger_bar]),
            "entry_reference": float(close[detected_at]),
        },
        metadata={
            "height": pat.height,
            "height_atr": pat.height / pat.atr if pat.atr else 0.0,
            "entry_reference_kind": "ACTIONABLE_CLOSE_NOT_FILL",
        },
    )


def detect_reversals(
    high: ArrayLike,
    low: ArrayLike,
    close: ArrayLike,
    config: ReversalConfig | None = None,
    kinds: tuple[Kind, ...] = ("DOUBLE", "HNS"),
) -> list[PatternDetection]:
    """All requested reversal detections, ordered by when they became actionable."""
    cfg = config or ReversalConfig()
    h, lo, c = as_hlc(high, low, close)
    atr_arr = atr(h, lo, c, ATR_PERIOD)  # Wilder ATR is causal: value i uses bars <= i
    found: list[PatternDetection] = []
    for mirrored, hh, ll, cc in ((False, h, lo, c), (True, -lo, -h, -c)):
        for pat, trigger_bar, detected_at in _scan_tops(hh, ll, cc, atr_arr, cfg=cfg, kinds=kinds):
            found.append(
                _to_detection(
                    pat,
                    trigger_bar=trigger_bar,
                    detected_at=detected_at,
                    close=c,
                    mirrored=mirrored,
                )
            )
    found.sort(key=lambda d: (d.actionable_at, d.pattern_id))
    return found


def make_detector(
    config: ReversalConfig | None = None, kinds: tuple[Kind, ...] = ("DOUBLE", "HNS")
) -> Callable[[ArrayLike, ArrayLike, ArrayLike], list[PatternDetection]]:
    """A ``Detector`` (see ``detection.py``) bound to a config, for the causality harness."""

    def detect(high: ArrayLike, low: ArrayLike, close: ArrayLike) -> list[PatternDetection]:
        return detect_reversals(high, low, close, config, kinds)

    return detect
