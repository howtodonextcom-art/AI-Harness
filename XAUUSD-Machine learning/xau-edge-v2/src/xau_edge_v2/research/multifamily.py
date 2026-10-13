"""MULTIFAMILY_RESEARCH_0.1.0: the complete signal CONTRACT of families B, C and D (no outcome).

Independent of CAND_V2_CORE_1.1.0 (they are never merged). For every raw eligibility of a family
(``core.intelligence.families``) this module builds the order the family WOULD plan, with the same
geometry code as the control (``core.risk``), and says which gate stops it. It never looks at what
price did afterwards: no outcome, no PnL.

Contract (spec: ``docs/research/multifamily_0.1.0.spec.json``; research only, authority NONE):

* entry quote  BUY at the ask (close + the bar's spread), SELL at the bid (the bar's close), prices
               in the broker's BID chart;
* stop         ``compute_stop`` (the control's): the family's invalidation level + 0.1 ATR, floored
               at 1.25 ATR, REFUSED above 3 ATR;
* target       ``compute_targets`` (the control's): 2R, capped by the opposing level; refused when
               net R:R < 1.5 or the room is gone. Opposing level: B and C the nearest unbroken M15
               structure level, D the opposite boundary of the 20-bar range;
* cost         cost_R = (spread + 2 x 3 points slippage) / risk <= 0.15 (the C2 screen, a screen and
               never a deduction);
* clearance    the opposing level at least 1 ATR away (the control's room rule);
* expiry       a signal can be acted on for 3 bars of the signal timeframe after it is known;
* episodes      eligibilities of one family and side within 6 bars are ONE episode (its first);
* overlap      one open position per branch: a signal inside the maximum-hold window (96 bars) of an
               earlier accepted signal of the same branch is flagged OVERLAP (reported, not hidden).

No constant was fitted. A change is a new spec version.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

import numpy as np

from xau_edge_v2.core import indicators as ind
from xau_edge_v2.core import structure as st
from xau_edge_v2.core.frames import Frame, from_micros
from xau_edge_v2.core.intelligence import families as fam
from xau_edge_v2.core.market_state import trading_session
from xau_edge_v2.core.risk import (
    MIN_NET_RR,
    SymbolSpec,
    compute_stop,
    compute_targets,
)

POINT = 0.01
SLIPPAGE_POINTS = 3.0
COST_R_MAX = 0.15
MIN_CLEAR_ATR = 1.0
EPISODE_BARS = 6
EXPIRY_BARS = 3
MAX_HOLD_BARS = 96
RANGE_LOOKBACK = fam.RANGE_LOOKBACK
SPEC = SymbolSpec()

GATES = ("EPISODE", "CLEARANCE", "STOP", "TARGET", "COST")
"""Order in which the first refusing gate is named."""


@dataclass(frozen=True)
class MfRecord:
    family: str
    side: int
    index: int
    known_at_us: int
    episode_head: bool
    entry: float
    stop: float | None
    target: float | None
    risk_atr: float | None
    net_rr: float | None
    cost_r: float | None
    opposing_atr: float | None
    capped_by_structure: bool
    expiry_us: int
    session: str
    regime: str | None
    first_refusal: str | None
    """None when every gate passes (ACCEPTED, before the overlap rule)."""
    overlap: bool
    """Inside the max-hold window of an earlier accepted signal of the same branch."""

    @property
    def accepted(self) -> bool:
        return self.first_refusal is None


def _opposing_level(
    family: str, side: int, i: int, f: Frame, res: st.StructureResult
) -> float | None:
    if family == "D":  # the opposite boundary of the range the setup lives in
        window = slice(i - RANGE_LOOKBACK, i)
        return float(f.high[window].max() if side > 0 else f.low[window].min())
    level = res.resistance[i] if side > 0 else res.support[i]
    return None if not np.isfinite(level) else float(level)


def evaluate_frame(frame: Frame) -> list[MfRecord]:  # noqa: PLR0912 - one gate per branch
    """Every raw eligibility of B, C and D on ``frame`` with its planned order and first refusal."""
    atr = ind.atr(frame.high, frame.low, frame.close, 14)
    adx = ind.adx(frame.high, frame.low, frame.close, 14)
    regime = st.classify_regime(
        adx=adx.adx, plus_di=adx.plus_di, minus_di=adx.minus_di, atr=atr,
        high=frame.high, low=frame.low, vol_window=min(200, frame.height),
        min_history=min(60, frame.height),
    )  # fmt: skip
    res = st.analyse_structure(frame.high, frame.low, frame.close)
    out: list[MfRecord] = []
    for name, signals in fam.all_families(frame).items():
        last_head: dict[int, int] = {}
        accepted_until = -1
        for s in signals:
            i = s.index
            a = float(atr[i])
            head = s.side not in last_head or i - last_head[s.side] > EPISODE_BARS
            if head:
                last_head[s.side] = i
            spread_price = float(frame.spread[i]) * POINT
            entry = float(frame.close[i]) + (spread_price if s.side > 0 else 0.0)
            refusal: str | None = None
            stop = target = risk_atr = net = cost_r = opp_atr = None
            capped = False
            opposing = _opposing_level(name, s.side, i, frame, res)
            if opposing is not None:
                opp_atr = abs(opposing - float(frame.close[i])) / a
            if not head:
                refusal = "EPISODE"
            elif opposing is not None and (
                (opposing - entry if s.side > 0 else entry - opposing) < MIN_CLEAR_ATR * a
            ):
                refusal = "CLEARANCE"
            else:
                stp = compute_stop(s.side, entry, s.invalidation, a)
                if stp is None or stp.distance < SPEC.min_stop_distance():
                    refusal = "STOP"
                else:
                    stop, risk_atr = stp.price, stp.distance / a
                    tg = compute_targets(
                        s.side, entry, stp, spread=spread_price, atr=a, opposing_level=opposing
                    )
                    if tg is None:
                        refusal = "TARGET"
                    else:
                        target, net, capped = tg.tp1, tg.net_rr, tg.capped_by_structure
                        cost_r = (spread_price + 2 * SLIPPAGE_POINTS * POINT) / stp.distance
                        if cost_r > COST_R_MAX:
                            refusal = "COST"
            overlap = False
            if refusal is None:
                overlap = i <= accepted_until
                if not overlap:
                    accepted_until = i + MAX_HOLD_BARS
            known = int(frame.available_us[i])
            at = from_micros(known).astimezone(UTC)
            out.append(
                MfRecord(
                    family=name, side=s.side, index=i, known_at_us=known, episode_head=head,
                    entry=entry, stop=stop, target=target, risk_atr=risk_atr, net_rr=net,
                    cost_r=cost_r, opposing_atr=opp_atr, capped_by_structure=capped,
                    expiry_us=known + EXPIRY_BARS * frame.timeframe.seconds * 1_000_000,
                    session=trading_session(datetime.fromtimestamp(at.timestamp(), UTC)),
                    regime=None if regime[i] is None else str(regime[i]),
                    first_refusal=refusal, overlap=overlap,
                )
            )  # fmt: skip
    return sorted(out, key=lambda r: (r.index, r.family))


__all__ = ["GATES", "MIN_NET_RR", "MfRecord", "evaluate_frame"]
