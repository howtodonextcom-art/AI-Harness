"""Wolfe Wave candidate detector (research tool, not a signal source).

Source of the rules: a single educational video (see ``docs/video-intelligence``), cross-checked
only against the geometry it draws. Published definitions differ, so every contested rule is a
config flag instead of a silent choice. Nothing here is validated as profitable: a candidate is a
geometric match, never a trade recommendation.

Bullish geometry (the bearish case is the exact mirror, found by negating prices):

* five alternating confirmed pivots: P1 low, P2 high, P3 low, P4 high, P5 low;
* lower line through P1-P3, upper line through P2-P4; they must converge (a wedge);
* P3 below P1, P4 below P2 (descending wedge), P4 between P3 and P2;
* P5 is the overshoot: it must close beyond the P1-P3 line (flag ``require_p5_beyond_line13``);
* entry is the close of the bar on which P5 becomes *confirmed* (``right`` bars after P5), stop is
  P5, target is the P1-P4 line (the "EPA" line) read ``target_horizon_bars`` after P5's index.

No look-ahead: pivots come from ``analyse_structure`` which only reveals a pivot ``right`` bars
after it formed, and a candidate is emitted at the bar that confirms P5, using nothing later.
"""

from __future__ import annotations

from itertools import pairwise
from typing import Literal, NamedTuple

import numpy as np
from numpy.typing import ArrayLike
from pydantic import BaseModel, ConfigDict, Field

from xau_edge.features.indicators import as_hlc
from xau_edge.structure.detection import (
    PatternDetection,
    PatternPoint,
    make_pattern_id,
)
from xau_edge.structure.pivots import Pivot, alternate, confirmed_pivots


class WolfeConfig(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    pivot_left: int = Field(default=3, ge=1)
    pivot_right: int = Field(default=3, ge=1)
    require_p5_beyond_line13: bool = True  # contested: some authors accept P5 on the line
    require_converging: bool = True
    require_p4_inside_p2_p3: bool = True
    min_leg_bars: int = Field(default=3, ge=1)  # minimum spacing between consecutive pivots
    max_pattern_bars: int = Field(default=400, ge=10)  # P1..P5 must fit in this span
    target_horizon_bars: int | None = None  # None: P5.bar - P3.bar bars after P5
    min_reward_risk: float = Field(default=1.0, ge=0.0)  # reject candidates below this R:R
    spread: float = Field(default=0.0, ge=0.0)  # price units added to the cost of entry
    entry_trigger: Literal["P5_CONFIRMED", "LINE13_RECLAIM"] = "P5_CONFIRMED"
    """Contested: enter when P5 is confirmed, or only after a close back inside line 1-3."""
    max_reclaim_bars: int = Field(default=20, ge=1)  # LINE13_RECLAIM only: how long to wait
    target_time: Literal["P5_MINUS_P3", "LINES_INTERSECTION"] = "P5_MINUS_P3"
    """Where on line 1-4 the target is read. ``P5_MINUS_P3`` is this project's own convention (no
    source uses it); ``LINES_INTERSECTION`` is the sourced ETA: where lines 2-4 and 1-3 meet."""
    max_eta_bars: int | None = Field(default=None, ge=1)  # drop an ETA further than this past P5


class WolfeCandidate(NamedTuple):
    side: Literal["BUY", "SELL"]
    pivots: tuple[Pivot, Pivot, Pivot, Pivot, Pivot]
    confirmed_at: int  # bar index at which this candidate first exists (no earlier information)
    entry: float
    stop: float
    target: float
    reward_risk: float
    geometry_known_at: int = -1  # when P5 became confirmed (== confirmed_at unless a reclaim waits)
    trigger_bar: int = (
        -1
    )  # where the trigger happened (the reclaim close; P5 confirmation otherwise)


def _line(p: Pivot, q: Pivot) -> tuple[float, float]:
    slope = (q.price - p.price) / (q.bar - p.bar)
    return slope, p.price - slope * p.bar


class _Lines(NamedTuple):
    s13: float
    b13: float
    s14: float
    b14: float
    s24: float = 0.0
    b24: float = 0.0


def _geometry(five: list[Pivot], cfg: WolfeConfig) -> _Lines | None:  # noqa: PLR0911
    """The geometric rules only (a bullish pattern on P1 low ... P5 low; the caller mirrors)."""
    p1, p2, p3, p4, p5 = five
    if p5.bar - p1.bar > cfg.max_pattern_bars:
        return None
    if any(b.bar - a.bar < cfg.min_leg_bars for a, b in pairwise(five)):
        return None
    if not (p3.price < p1.price and p4.price < p2.price and p2.price > p1.price):
        return None
    if cfg.require_p4_inside_p2_p3 and not (p3.price < p4.price < p2.price):
        return None
    s13, b13 = _line(p1, p3)
    s24, b24 = _line(p2, p4)
    if cfg.require_converging and not (s24 < s13):  # upper line falls faster: gap narrows
        return None
    if cfg.require_p5_beyond_line13 and not (p5.price < s13 * p5.bar + b13):
        return None
    if not p5.price < p3.price:
        return None
    s14, b14 = _line(p1, p4)
    return _Lines(s13, b13, s14, b14, s24, b24)


def _plan(
    five: list[Pivot],
    lines: _Lines,
    *,
    entry_bar: int,
    close: np.ndarray,  # type: ignore[type-arg,unused-ignore]
    cfg: WolfeConfig,
) -> WolfeCandidate | None:
    """Entry, stop and target for a geometry that is actionable at ``entry_bar``."""
    p3, p5 = five[2], five[4]
    if cfg.target_time == "LINES_INTERSECTION":
        eta = (lines.b24 - lines.b13) / (lines.s13 - lines.s24) if lines.s13 != lines.s24 else None
        if eta is None or eta <= entry_bar:
            return None  # the lines never meet ahead of the entry: there is no sourced ETA
        if cfg.max_eta_bars is not None and eta - p5.bar > cfg.max_eta_bars:
            return None
        target = lines.s14 * eta + lines.b14
    else:
        horizon = (
            cfg.target_horizon_bars if cfg.target_horizon_bars is not None else p5.bar - p3.bar
        )
        target = lines.s14 * (p5.bar + horizon) + lines.b14
    entry = float(close[entry_bar]) + cfg.spread
    risk = entry - p5.price
    reward = target - entry
    if risk <= 0 or reward <= 0 or reward / risk < cfg.min_reward_risk:
        return None
    return WolfeCandidate(
        "BUY",
        (five[0], five[1], p3, five[3], p5),
        entry_bar,
        entry,
        p5.price,
        target,
        reward / risk,
    )


def _await_reclaim(
    five: list[Pivot],
    lines: _Lines,
    low: np.ndarray,  # type: ignore[type-arg,unused-ignore]
    close: np.ndarray,  # type: ignore[type-arg,unused-ignore]
    cfg: WolfeConfig,
) -> tuple[int, int] | None:
    """The first close back above line 1-3 after P5, as ``(trigger_bar, bar it is knowable)``.

    The stop is P5: if a low pierces it first, the setup is dead. Bars up to P5's confirmation are
    scanned too (their data is known by then); the trigger is never reported before P5 itself is.
    """
    p5 = five[4]
    limit = min(p5.confirmed_at + cfg.max_reclaim_bars, close.size - 1)
    for k in range(p5.bar + 1, limit + 1):
        if low[k] < p5.price:
            return None
        if close[k] > lines.s13 * k + lines.b13:
            return k, max(k, p5.confirmed_at)
    return None


def detect_wolfe(
    high: ArrayLike, low: ArrayLike, close: ArrayLike, config: WolfeConfig | None = None
) -> list[WolfeCandidate]:
    """All Wolfe Wave candidates, each emitted at the bar where the chosen trigger is knowable:
    P5's confirmation (default) or the first close back inside line 1-3 (``LINE13_RECLAIM``)."""
    cfg = config or WolfeConfig()
    h, lo, c = as_hlc(high, low, close)
    out: list[WolfeCandidate] = []
    for side, hh, ll, cc in (("BUY", h, lo, c), ("SELL", -lo, -h, -c)):
        history: list[Pivot] = []
        for pivot in confirmed_pivots(hh, ll, cc, left=cfg.pivot_left, right=cfg.pivot_right):
            alternate(history, pivot)
            if len(history) < 5 or history[-1] is not pivot or pivot.kind != "L":
                continue
            five = history[-5:]
            lines = _geometry(five, cfg)
            if lines is None:
                continue
            known = pivot.confirmed_at
            if cfg.entry_trigger == "P5_CONFIRMED":
                trigger, entry_bar = known, known
            else:
                hit = _await_reclaim(five, lines, ll, cc, cfg)
                if hit is None:
                    continue
                trigger, entry_bar = hit
            cand = _plan(five, lines, entry_bar=entry_bar, close=cc, cfg=cfg)
            if cand is None:
                continue
            cand = cand._replace(geometry_known_at=known, trigger_bar=trigger)
            if side == "SELL":  # mirror back to real prices
                mirrored = tuple(
                    Pivot(p.bar, -p.price, "H" if p.kind == "L" else "L", p.confirmed_at)
                    for p in cand.pivots
                )
                cand = cand._replace(
                    side="SELL",
                    pivots=mirrored,  # type: ignore[arg-type]
                    entry=-cand.entry,
                    stop=-cand.stop,
                    target=-cand.target,
                )
            out.append(cand)
    out.sort(key=lambda x: x.confirmed_at)
    return out


WOLFE_DEFINITION = "wolfe/convention-v1 (P5 beyond line 1-3, converging, P1-P4 target; see docs)"


def to_detection(candidate: WolfeCandidate, config: WolfeConfig | None = None) -> PatternDetection:
    """The common contract. The three bar indexes differ only in ``LINE13_RECLAIM`` mode."""
    cfg = config or WolfeConfig()
    points = tuple(
        PatternPoint(label=f"P{i + 1}", bar=p.bar, price=p.price, confirmed_at=p.confirmed_at)
        for i, p in enumerate(candidate.pivots)
    )
    known = candidate.geometry_known_at
    if known < 0:
        known = candidate.confirmed_at
    trigger = candidate.trigger_bar if candidate.trigger_bar >= 0 else candidate.confirmed_at
    return PatternDetection(
        pattern_id=make_pattern_id("WOLFE_WAVE", points) + cfg.entry_trigger[:1],
        pattern_type="WOLFE_WAVE",
        bias="LONG" if candidate.side == "BUY" else "SHORT",
        points=points,
        geometry_known_at=known,
        detected_at=candidate.confirmed_at,
        actionable_at=candidate.confirmed_at,
        trigger_bar=trigger,
        trigger_delay_bars=candidate.confirmed_at - trigger,
        source_definition=f"{WOLFE_DEFINITION}; trigger={cfg.entry_trigger}",
        reference_levels={
            "entry_reference": candidate.entry,
            "stop_reference": candidate.stop,
            "target_reference": candidate.target,
        },
        metadata={"reward_risk_reference": candidate.reward_risk},
    )


def detect_wolfe_patterns(
    high: ArrayLike, low: ArrayLike, close: ArrayLike, config: WolfeConfig | None = None
) -> list[PatternDetection]:
    """``detect_wolfe`` through the common detection contract."""
    return [to_detection(c, config) for c in detect_wolfe(high, low, close, config)]
