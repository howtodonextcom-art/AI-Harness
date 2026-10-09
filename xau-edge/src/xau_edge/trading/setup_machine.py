"""Setup lifecycle (baseline v1.2): NONE -> ARMED -> TRIGGERED, or EXPIRED / INVALIDATED.

A pullback is a counter-move and the trigger is the resumption of the trend, so requiring both on
the same bar (v1.1) conflicts with the concept: the two are negatively associated (see
``docs/reports/SIGNAL_FUNNEL_ANALYSIS.md``). The lifecycle lets the M15 setup ARM and the M5
trigger fire LATER, within ``valid_bars`` M5 closes.

It is a pure function of the closed bars up to ``at`` (no stored state, no clock): it replays the
last ``lookback`` M5 closes through the machine, so live, replay and paper always agree, a restart
loses nothing and there is no hidden persistence. The labels at each past close come from the same
functions as the market state (H1 trend, M15 structure and pullback, M5 momentum) evaluated on the
bars that had closed at THAT time, so nothing from the future leaks into an earlier step.

Rules (pre-registered in ``docs/trading/BASELINE_V1_2_PREREGISTRATION.md``):

* ARMED when H1 has a direction and the M15 setup is ready, on the rising edge (it was not ready
  on the previous close) or on the first close of the window;
* an ARMED setup lives ``valid_bars`` M5 closes (EXPIRED afterwards) and is INVALIDATED when the H1
  direction changes or the M15 structure turns against it;
* TRIGGERED at the first close with M5 momentum in the direction; a new setup is armed only after
  the M15 setup stops being ready and becomes ready again (one signal per pullback);
* the desk signal fires only when the TRIGGER is the current (newest) close.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

import polars as pl

from xau_edge.domain.timeframe import Timeframe
from xau_edge.trading.frames import MultiTfBars
from xau_edge.trading.market_state import (
    SnapshotMemo,
    StateConfig,
    TfSnapshot,
    _h1_trend,
    _m5_momentum,
    _pullback,
    _structure_label,
)

VALID_BARS = 6
LOOKBACK = 36
_TFS = (Timeframe.H1, Timeframe.M15, Timeframe.M5)


class SetupPhase(StrEnum):
    NONE = "NONE"
    ARMED = "ARMED"
    TRIGGERED = "TRIGGERED"
    EXPIRED = "EXPIRED"
    INVALIDATED = "INVALIDATED"


@dataclass(frozen=True)
class SetupLifecycle:
    phase: SetupPhase
    side: int  # +1 buy, -1 sell, 0 none
    armed_at: datetime | None
    trigger_at: datetime | None
    bars_since_armed: int | None
    fires: bool
    """True only when the trigger is the newest close (the desk may signal now)."""
    reason: str


@dataclass(frozen=True)
class _Labels:
    side: int
    ready: bool
    against: bool
    trigger: bool


def _labels_at(
    bars: MultiTfBars, at: datetime, cfg: StateConfig, memo: SnapshotMemo
) -> _Labels | None:
    snaps: dict[Timeframe, TfSnapshot | None] = {}
    for tf in _TFS:
        closed = bars.as_of(tf, at)
        if closed is None:
            return None
        snaps[tf] = memo.get(closed, tf, cfg)
    h1 = _h1_trend(snaps[Timeframe.H1])
    side = 1 if h1 == "BULLISH" else -1 if h1 == "BEARISH" else 0
    if side == 0:
        return _Labels(0, False, False, False)
    structure = _structure_label(snaps[Timeframe.M15])
    pullback = _pullback(snaps[Timeframe.M15])
    with_trend, against = ("UP", "DOWN") if side > 0 else ("DOWN", "UP")
    want = "PULLBACK_IN_UPTREND" if side > 0 else "PULLBACK_IN_DOWNTREND"
    return _Labels(
        side=side,
        ready=structure == with_trend and pullback == want,
        against=structure == against,
        trigger=_m5_momentum(snaps[Timeframe.M5]) == with_trend,
    )


def lifecycle(
    bars: MultiTfBars,
    at: datetime,
    *,
    cfg: StateConfig | None = None,
    memo: SnapshotMemo | None = None,
    valid_bars: int = VALID_BARS,
    lookback: int = LOOKBACK,
) -> SetupLifecycle:
    """The setup lifecycle at ``at`` from closed bars only."""
    cfg = cfg or StateConfig()
    memo = memo or SnapshotMemo()
    m5 = bars.frames.get(Timeframe.M5)
    if m5 is None:
        return SetupLifecycle(SetupPhase.NONE, 0, None, None, None, False, "no M5 bars")
    closes = m5.filter(pl.col("available_at") <= at)["available_at"].tail(lookback).to_list()
    phase, side = SetupPhase.NONE, 0
    armed_idx: int | None = None
    trig_idx: int | None = None
    reason = "no setup"
    ready_prev: bool | None = None
    for idx, close in enumerate(closes):
        lab = _labels_at(bars, close, cfg, memo)
        if lab is None:
            return SetupLifecycle(SetupPhase.NONE, 0, None, None, None, False, "missing timeframe")
        if phase is SetupPhase.ARMED:
            if lab.side != side:
                phase, reason = SetupPhase.INVALIDATED, "H1 direction changed"
            elif lab.against:
                phase, reason = SetupPhase.INVALIDATED, "M15 structure turned against the setup"
            elif armed_idx is not None and idx - armed_idx > valid_bars:
                phase, reason = SetupPhase.EXPIRED, f"no M5 trigger within {valid_bars} bars"
        elif phase is SetupPhase.TRIGGERED and (not lab.ready or lab.side != side):
            phase, reason = SetupPhase.NONE, "pullback finished"
        edge = lab.ready and (ready_prev is None or ready_prev is False)
        if phase in (SetupPhase.NONE, SetupPhase.EXPIRED, SetupPhase.INVALIDATED) and edge:
            phase, side, armed_idx, trig_idx = SetupPhase.ARMED, lab.side, idx, None
            reason = "M15 pullback in the H1 trend is ready"
        if phase is SetupPhase.ARMED and lab.trigger and lab.side == side and not lab.against:
            phase, trig_idx = SetupPhase.TRIGGERED, idx
            reason = "M5 trigger after an armed M15 setup"
        ready_prev = lab.ready
        if phase in (SetupPhase.NONE, SetupPhase.EXPIRED, SetupPhase.INVALIDATED):
            side = 0 if phase is SetupPhase.NONE else side
    last = len(closes) - 1
    return SetupLifecycle(
        phase=phase,
        side=side,
        armed_at=None if armed_idx is None else closes[armed_idx],
        trigger_at=None if trig_idx is None else closes[trig_idx],
        bars_since_armed=None if armed_idx is None else last - armed_idx,
        fires=phase is SetupPhase.TRIGGERED and trig_idx == last,
        reason=reason,
    )
