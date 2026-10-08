"""Position sizing from a fixed fraction of equity at risk."""

from __future__ import annotations

import math


def position_size(
    equity: float,
    risk_fraction: float,
    stop_distance: float,
    *,
    contract_size: float,
    min_lot: float = 0.01,
    lot_step: float = 0.01,
    max_lot: float = 100.0,
) -> float:
    """Lots such that hitting the stop loses at most ``risk_fraction`` of ``equity``.

    ``stop_distance`` is in price units; one lot loses ``stop_distance * contract_size`` at the
    stop. The result is rounded DOWN to ``lot_step`` (never up, so the budget is never exceeded),
    capped at ``max_lot``, and 0.0 when even ``min_lot`` would exceed the budget.
    """
    for name, value in (("equity", equity), ("stop_distance", stop_distance)):
        if not (math.isfinite(value) and value > 0):
            msg = f"{name} must be a positive finite number, got {value}"
            raise ValueError(msg)
    if not (math.isfinite(risk_fraction) and 0 < risk_fraction <= 0.1):
        msg = f"risk_fraction must be within (0, 0.1], got {risk_fraction}"
        raise ValueError(msg)
    raw = equity * risk_fraction / (stop_distance * contract_size)
    lots = math.floor(raw / lot_step + 1e-9) * lot_step
    lots = min(lots, max_lot)
    if lots < min_lot - 1e-12:
        return 0.0
    return round(lots, 8)
