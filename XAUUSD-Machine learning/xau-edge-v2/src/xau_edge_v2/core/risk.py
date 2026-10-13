"""Stops, targets and THE position-size function (the only one in V2: ADR-V2-010).

* The stop comes from market structure plus a buffer, floored at ``atr_k`` x ATR, refused when
  wider than ``max_stop_atr`` x ATR (hybrid model, fixed in advance, never tuned on results).
* Targets are an R multiple capped by the next opposing level and are always judged AFTER the
  spread: ``net_rr = (reward - spread) / (risk + spread)``.
* The size is computed from the BROKER's contract spec (``tick_size``/``tick_value``), rounded DOWN
  to the volume step, the real risk is recomputed after rounding, and the trade is refused when even
  the minimum volume exceeds the cap or the stop is closer than the broker's minimum stop distance.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

ATR_K = 1.25
STRUCTURE_BUFFER_ATR = 0.1
MAX_STOP_ATR = 3.0
R_MULTIPLE = 2.0
TP2_R_MULTIPLE = 3.0
MIN_NET_RR = 1.5
STRUCTURE_TARGET_BUFFER_ATR = 0.1
MAX_RISK_PCT = 2.0


@dataclass(frozen=True)
class SymbolSpec:
    """Contract specification of one symbol (every value comes from the broker)."""

    point: float = 0.01
    tick_size: float = 0.01
    tick_value: float = 1.0
    """Account-currency profit of ONE tick for ONE lot."""
    contract_size: float = 100.0
    volume_min: float = 0.01
    volume_max: float = 100.0
    volume_step: float = 0.01
    stops_level_points: int = 0
    freeze_level_points: int = 0
    digits: int = 2

    def loss_per_lot(self, distance: float) -> float:
        """Account-currency loss of one lot when price moves ``distance`` against the position."""
        return distance / self.tick_size * self.tick_value

    def min_stop_distance(self) -> float:
        return self.stops_level_points * self.point


@dataclass(frozen=True)
class Stop:
    price: float
    distance: float
    model: str


@dataclass(frozen=True)
class Targets:
    tp1: float
    tp2: float | None
    gross_rr: float
    net_rr: float
    required_win_rate: float
    capped_by_structure: bool


@dataclass(frozen=True)
class SizeResult:
    lots: float
    risk_amount: float
    risk_pct_actual: float
    reasons: tuple[str, ...]

    @property
    def allowed(self) -> bool:
        return self.lots > 0 and not self.reasons


def compute_stop(
    direction: int, entry: float, swing_level: float | None, atr: float
) -> Stop | None:
    """The hybrid stop for ``direction`` (+1 buy, -1 sell), or None when none is acceptable."""
    if direction not in (-1, 1) or atr <= 0 or entry <= 0:
        return None
    atr_distance = ATR_K * atr
    structure_distance: float | None = None
    if swing_level is not None:
        raw = (entry - swing_level) if direction > 0 else (swing_level - entry)
        if raw > 0:
            structure_distance = raw + STRUCTURE_BUFFER_ATR * atr
    distance = max(structure_distance or 0.0, atr_distance)
    if distance <= 0 or distance > MAX_STOP_ATR * atr:
        return None
    return Stop(price=entry - direction * distance, distance=distance, model="HYBRID")


def compute_targets(
    direction: int,
    entry: float,
    stop: Stop,
    *,
    spread: float,
    atr: float,
    opposing_level: float | None = None,
) -> Targets | None:
    """TP1 (and TP2 when not capped), with the net payoff; None when the net R/R is too low."""
    risk = stop.distance
    reward = R_MULTIPLE * risk
    capped = False
    if opposing_level is not None:
        room = (opposing_level - entry) if direction > 0 else (entry - opposing_level)
        room -= STRUCTURE_TARGET_BUFFER_ATR * atr
        if 0 < room < reward:
            reward, capped = room, True
        elif room <= 0:
            return None
    gross = reward / risk
    net = (reward - spread) / (risk + spread)
    if net < MIN_NET_RR:
        return None
    tp2 = None if capped else entry + direction * TP2_R_MULTIPLE * risk
    return Targets(
        tp1=entry + direction * reward,
        tp2=tp2,
        gross_rr=gross,
        net_rr=net,
        required_win_rate=1.0 / (1.0 + net),
        capped_by_structure=capped,
    )


def size_for_risk(  # noqa: PLR0911 - one early exit per refusal
    equity: float,
    risk_pct: float,
    entry: float,
    stop_loss: float,
    spec: SymbolSpec,
    *,
    max_risk_pct: float | None = None,
) -> SizeResult:
    """Largest volume (rounded down) whose stop loss costs at most ``risk_pct`` of equity."""
    if not (math.isfinite(equity) and equity > 0):
        return SizeResult(0.0, 0.0, 0.0, ("INVALID_EQUITY",))
    if not (math.isfinite(risk_pct) and 0 < risk_pct <= MAX_RISK_PCT):
        return SizeResult(0.0, 0.0, 0.0, ("INVALID_RISK_PCT",))
    distance = abs(entry - stop_loss)
    if not (math.isfinite(distance) and distance > 0):
        return SizeResult(0.0, 0.0, 0.0, ("INVALID_STOP",))
    if distance < spec.min_stop_distance():
        return SizeResult(0.0, 0.0, 0.0, ("STOP_TOO_CLOSE_FOR_BROKER",))
    loss_lot = spec.loss_per_lot(distance)
    budget = equity * risk_pct / 100.0
    steps = math.floor(budget / loss_lot / spec.volume_step + 1e-9)
    lots = min(steps * spec.volume_step, spec.volume_max)
    if lots < spec.volume_min - 1e-12:
        return SizeResult(0.0, 0.0, 0.0, ("MIN_LOT_EXCEEDS_RISK",))
    lots = round(lots, 8)
    risk_amount = lots * loss_lot
    actual_pct = risk_amount / equity * 100.0
    cap = max_risk_pct if max_risk_pct is not None else risk_pct
    if actual_pct > cap + 1e-9:
        return SizeResult(0.0, 0.0, actual_pct, ("RISK_ABOVE_CAP_AFTER_ROUNDING",))
    return SizeResult(lots, risk_amount, actual_pct, ())
