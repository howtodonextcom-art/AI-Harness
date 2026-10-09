"""The owner's risk calculator: equity + risk % + entry + SL -> risk amount, SL distance, lot size.

Pure and read-only: it computes, it never sends anything. The contract specification (tick size,
tick value, volume limits, stop level) is the BROKER's, never hard-coded; lots are rounded DOWN to
the broker's volume step so the real risk never exceeds the chosen percentage. Changing the risk
percentage changes only the lot size and the money amounts: never the signal, entry, SL or TP.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from xau_edge.trading.sizing import SymbolSpec, size_for_risk

RISK_CHOICES = (0.10, 0.25, 0.50)
"""Risk percentages the desk offers (configurable, hard-capped by MAX_RISK_PCT)."""
MAX_RISK_PCT = 0.50
DEFAULT_RISK_PCT = 0.25


@dataclass(frozen=True)
class RiskPlan:
    """The money side of a trade plan."""

    ok: bool
    lots: float
    risk_pct: float
    risk_pct_actual: float
    risk_amount: float
    sl_distance: float
    tp_distance: float | None
    tick_value: float
    loss_at_sl: float
    gain_at_tp: float | None
    errors: tuple[str, ...]

    def as_dict(self) -> dict[str, object]:
        return {
            "ok": self.ok,
            "lots": self.lots,
            "risk_pct": self.risk_pct,
            "risk_pct_actual": round(self.risk_pct_actual, 4),
            "risk_amount": round(self.risk_amount, 2),
            "sl_distance": round(self.sl_distance, 5),
            "tp_distance": None if self.tp_distance is None else round(self.tp_distance, 5),
            "tick_value": self.tick_value,
            "loss_at_sl": round(self.loss_at_sl, 2),
            "gain_at_tp": None if self.gain_at_tp is None else round(self.gain_at_tp, 2),
            "errors": list(self.errors),
        }


def calculate(
    *,
    equity: float,
    risk_pct: float,
    entry: float,
    stop_loss: float,
    spec: SymbolSpec,
    take_profit: float | None = None,
    allowed: tuple[float, ...] = RISK_CHOICES,
) -> RiskPlan:
    """Lot size and money amounts; ``ok`` is False (lots 0) with reasons if it cannot be sized."""
    errors: list[str] = []
    if not any(math.isclose(risk_pct, a, abs_tol=1e-9) for a in allowed) or risk_pct > MAX_RISK_PCT:
        errors.append("RISK_PCT_NOT_ALLOWED")
    if not all(math.isfinite(v) for v in (equity, entry, stop_loss)):
        errors.append("INVALID_INPUT")
    sl_distance = abs(entry - stop_loss) if not errors else 0.0
    tp_distance = abs(take_profit - entry) if take_profit is not None and not errors else None
    if errors:
        return RiskPlan(
            False,
            0.0,
            risk_pct,
            0.0,
            0.0,
            sl_distance,
            tp_distance,
            spec.tick_value,
            0.0,
            None,
            tuple(errors),
        )
    sized = size_for_risk(equity, risk_pct, entry, stop_loss, spec, max_risk_pct=MAX_RISK_PCT)
    per_lot_loss = spec.loss_per_lot(sl_distance)
    gain = (
        None
        if tp_distance is None or not sized.allowed
        else sized.lots * spec.loss_per_lot(tp_distance)
    )
    return RiskPlan(
        ok=sized.allowed,
        lots=sized.lots,
        risk_pct=risk_pct,
        risk_pct_actual=sized.risk_pct_actual,
        risk_amount=sized.risk_amount,
        sl_distance=sl_distance,
        tp_distance=tp_distance,
        tick_value=spec.tick_value,
        loss_at_sl=sized.lots * per_lot_loss if sized.allowed else 0.0,
        gain_at_tp=gain,
        errors=sized.reasons,
    )
