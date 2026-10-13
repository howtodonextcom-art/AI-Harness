"""RESEARCH ONLY: entry-eligibility of three strategy families that differ from the V1 chain.

This module says WHEN a family's setup is eligible (side, reference price, invalidation level) from
closed bars only. It has no stop/target/size logic, no outcome, and no caller in the live system
(a test pins that). Whether any of them has an edge is NOT_TESTED: the protocol and the hypothesis
ledger are in ``docs/research/``; the families are STRATEGY_HYPOTHESIS, not strategies.

Family B  breakout continuation: a close beyond a TIGHT 12-bar box by a decisive bar
          (body >= 0.5 range); invalidation = the opposite side of the box.
Family C  reversal after a failed breakout: a sweep bar (FAILED_BREAKOUT_x) followed within 6
          bars by a structure event (CHoCH or BOS) pointing the same way; invalidation = the
          sweep's extreme; eligible at the close of the confirming bar, not before.
Family D  range interaction: in a RANGE-labelled market, a wick rejection whose tip reaches the
          boundary of the last 20 bars (within 0.25 ATR); invalidation = the wick tip.

Constants are a-priori and frozen by the preregistration; none was fitted to a result.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.lib.stride_tricks import sliding_window_view

from xau_edge_v2.core import indicators as ind
from xau_edge_v2.core import structure as st
from xau_edge_v2.core.frames import Frame
from xau_edge_v2.core.intelligence import price_action as pa
from xau_edge_v2.core.intelligence import structure_events as se
from xau_edge_v2.core.intelligence import volatility as vol

BODY_SHARE = 0.5
CONFIRM_WINDOW = 6
RANGE_LOOKBACK = 20
RANGE_TOUCH_ATR = 0.25
FAMILIES = ("B", "C", "D")


@dataclass(frozen=True)
class FamilySignal:
    family: str
    side: int
    """+1 buy-side setup, -1 sell-side setup (a description of eligibility, not an order)."""
    index: int
    known_at_us: int
    reference_price: float
    """The close of the bar that made the setup eligible (no better price is assumed)."""
    invalidation: float
    risk_atr: float
    """|reference - invalidation| in ATR: how far the setup is from being wrong."""


def _atr(frame: Frame) -> np.ndarray:
    return ind.atr(frame.high, frame.low, frame.close, 14)


def _signal(
    f: Frame, atr: np.ndarray, family: str, side: int, i: int, inval: float
) -> FamilySignal:
    ref = float(f.close[i])
    return FamilySignal(
        family, side, i, int(f.available_us[i]), ref, float(inval), abs(ref - inval) / float(atr[i])
    )


def family_b(f: Frame) -> list[FamilySignal]:
    n, w = f.height, vol.BOX_BARS
    if n < w + 20:
        return []
    atr = _atr(f)
    rng = f.high - f.low
    hi = sliding_window_view(f.high, w).max(axis=1)  # window ending at j covers bars j-w+1..j
    lo = sliding_window_view(f.low, w).min(axis=1)
    mean_rng = sliding_window_view(rng, w).mean(axis=1)
    out: list[FamilySignal] = []
    for i in range(w, n):
        a = atr[i]
        if not np.isfinite(a) or a <= 0:
            continue
        box_hi, box_lo = hi[i - w], lo[i - w]  # the w bars BEFORE bar i
        valid = (box_hi - box_lo) <= vol.BOX_MAX_HEIGHT_ATR * a and mean_rng[
            i - w
        ] / a <= vol.BOX_MAX_MEAN_RANGE_ATR
        if not valid or rng[i] <= 0 or abs(f.close[i] - f.open[i]) < BODY_SHARE * rng[i]:
            continue
        if f.close[i] > box_hi and f.close[i] > f.open[i]:
            out.append(_signal(f, atr, "B", 1, i, float(box_lo)))
        elif f.close[i] < box_lo and f.close[i] < f.open[i]:
            out.append(_signal(f, atr, "B", -1, i, float(box_hi)))
    return out


def family_c(f: Frame) -> list[FamilySignal]:
    atr = _atr(f)
    sweeps = [e for e in pa.detect(f) if e.kind in ("FAILED_BREAKOUT_UP", "FAILED_BREAKOUT_DOWN")]
    events = [e for e in se.structure_events(f) if e.kind.startswith(("CHOCH", "BOS"))]
    out: list[FamilySignal] = []
    used: set[tuple[int, int]] = set()
    for s in sweeps:
        side = -1 if s.kind == "FAILED_BREAKOUT_UP" else 1  # a swept high points down
        for e in events:
            if not s.index < e.index <= s.index + CONFIRM_WINDOW:
                continue
            if (1 if e.kind.endswith("UP") else -1) != side or (side, e.index) in used:
                continue
            if s.invalidation is None or not np.isfinite(atr[e.index]) or atr[e.index] <= 0:
                continue
            used.add((side, e.index))
            out.append(_signal(f, atr, "C", side, e.index, s.invalidation))
            break
    return sorted(out, key=lambda x: x.index)


def family_d(f: Frame) -> list[FamilySignal]:
    n = f.height
    atr = _atr(f)
    adx = ind.adx(f.high, f.low, f.close, 14)
    regime = st.classify_regime(
        adx=adx.adx, plus_di=adx.plus_di, minus_di=adx.minus_di, atr=atr,
        high=f.high, low=f.low, vol_window=min(200, n), min_history=min(60, n),
    )  # fmt: skip
    out: list[FamilySignal] = []
    for e in pa.detect(f):
        i = e.index
        if e.kind not in ("UPPER_WICK_REJECTION", "LOWER_WICK_REJECTION") or i < RANGE_LOOKBACK:
            continue
        if regime[i] != "RANGE" or not np.isfinite(atr[i]) or atr[i] <= 0:
            continue
        top = float(f.high[i - RANGE_LOOKBACK : i].max())
        bottom = float(f.low[i - RANGE_LOOKBACK : i].min())
        if e.kind == "UPPER_WICK_REJECTION" and f.high[i] >= top - RANGE_TOUCH_ATR * atr[i]:
            out.append(_signal(f, atr, "D", -1, i, float(f.high[i])))
        if e.kind == "LOWER_WICK_REJECTION" and f.low[i] <= bottom + RANGE_TOUCH_ATR * atr[i]:
            out.append(_signal(f, atr, "D", 1, i, float(f.low[i])))
    return out


def all_families(f: Frame) -> dict[str, list[FamilySignal]]:
    return {"B": family_b(f), "C": family_c(f), "D": family_d(f)}
