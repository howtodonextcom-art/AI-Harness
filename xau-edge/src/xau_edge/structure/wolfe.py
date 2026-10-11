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
from xau_edge.structure.swings import StructureConfig, analyse_structure


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


class Pivot(NamedTuple):
    bar: int
    price: float
    kind: Literal["H", "L"]
    confirmed_at: int


class WolfeCandidate(NamedTuple):
    side: Literal["BUY", "SELL"]
    pivots: tuple[Pivot, Pivot, Pivot, Pivot, Pivot]
    confirmed_at: int  # bar index at which this candidate first exists (no earlier information)
    entry: float
    stop: float
    target: float
    reward_risk: float


def _pivots(high: ArrayLike, low: ArrayLike, close: ArrayLike, cfg: WolfeConfig) -> list[Pivot]:
    h, lo, c = as_hlc(high, low, close)
    res = analyse_structure(h, lo, c, StructureConfig(left=cfg.pivot_left, right=cfg.pivot_right))
    found: list[Pivot] = []
    for j in range(h.size):
        if res.new_swing_high[j]:
            found.append(Pivot(j - cfg.pivot_right, float(res.last_swing_high[j]), "H", j))
        if res.new_swing_low[j]:
            found.append(Pivot(j - cfg.pivot_right, float(res.last_swing_low[j]), "L", j))
    found.sort(key=lambda p: (p.confirmed_at, p.bar))
    return found


def _alternate(history: list[Pivot], new: Pivot) -> None:
    """Keep strictly alternating H/L; of two same-kind neighbours keep the more extreme one."""
    if history and history[-1].kind == new.kind:
        last = history[-1]
        better = new.price > last.price if new.kind == "H" else new.price < last.price
        if better:
            history[-1] = new
        return
    history.append(new)


def _line(p: Pivot, q: Pivot) -> tuple[float, float]:
    slope = (q.price - p.price) / (q.bar - p.bar)
    return slope, p.price - slope * p.bar


def _evaluate(  # noqa: PLR0911 - one early return per geometric rule reads best
    five: list[Pivot],
    close: np.ndarray,
    cfg: WolfeConfig,  # type: ignore[type-arg,unused-ignore]
) -> WolfeCandidate | None:
    """Evaluate a bullish pattern on ``five`` (P1 low ... P5 low); mirrored by the caller."""
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
    s24, _b24 = _line(p2, p4)
    if cfg.require_converging and not (s24 < s13):  # upper line falls faster: gap narrows
        return None
    if cfg.require_p5_beyond_line13 and not (p5.price < s13 * p5.bar + b13):
        return None
    if not p5.price < p3.price:
        return None
    s14, b14 = _line(p1, p4)
    horizon = cfg.target_horizon_bars if cfg.target_horizon_bars is not None else p5.bar - p3.bar
    target = s14 * (p5.bar + horizon) + b14
    entry = float(close[p5.confirmed_at]) + cfg.spread
    risk = entry - p5.price
    reward = target - entry
    if risk <= 0 or reward <= 0 or reward / risk < cfg.min_reward_risk:
        return None
    return WolfeCandidate(
        "BUY", (p1, p2, p3, p4, p5), p5.confirmed_at, entry, p5.price, target, reward / risk
    )


def detect_wolfe(
    high: ArrayLike, low: ArrayLike, close: ArrayLike, config: WolfeConfig | None = None
) -> list[WolfeCandidate]:
    """All Wolfe Wave candidates, each emitted at the bar that confirms its fifth pivot."""
    cfg = config or WolfeConfig()
    h, lo, c = as_hlc(high, low, close)
    out: list[WolfeCandidate] = []
    for side, hh, ll, cc in (("BUY", h, lo, c), ("SELL", -lo, -h, -c)):
        history: list[Pivot] = []
        for pivot in _pivots(hh, ll, cc, cfg):
            _alternate(history, pivot)
            if len(history) >= 5 and history[-1] is pivot and pivot.kind == "L":
                cand = _evaluate(history[-5:], cc, cfg)
                if cand is None:
                    continue
                if side == "SELL":  # mirror back to real prices
                    mirrored = tuple(
                        Pivot(p.bar, -p.price, "H" if p.kind == "L" else "L", p.confirmed_at)
                        for p in cand.pivots
                    )
                    cand = WolfeCandidate(
                        "SELL", mirrored,  # type: ignore[arg-type]
                        cand.confirmed_at, -cand.entry, -cand.stop, -cand.target, cand.reward_risk,
                    )  # fmt: skip
                out.append(cand)
    out.sort(key=lambda x: x.confirmed_at)
    return out
