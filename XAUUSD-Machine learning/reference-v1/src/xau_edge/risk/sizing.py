"""Position sizing from a fixed fraction of equity at risk.

Canonical lot math lives in ``xau_edge.trading.sizing.size_for_risk``. This wrapper keeps the
legacy ``position_size(equity, risk_fraction, stop_distance, contract_size=...)`` signature so
``RiskEngine`` does not invent a second formula.
"""

from __future__ import annotations

import math

from xau_edge.trading.sizing import SymbolSpec, size_for_risk


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

    Delegates to ``size_for_risk`` with a spec where ``tick_value / tick_size == contract_size``,
    so one lot loses ``stop_distance * contract_size``. The result is rounded DOWN.
    """
    for name, value in (("equity", equity), ("stop_distance", stop_distance)):
        if not (math.isfinite(value) and value > 0):
            msg = f"{name} must be a positive finite number, got {value}"
            raise ValueError(msg)
    if not (math.isfinite(risk_fraction) and 0 < risk_fraction <= 0.1):
        msg = f"risk_fraction must be within (0, 0.1], got {risk_fraction}"
        raise ValueError(msg)
    spec = SymbolSpec(
        tick_size=1.0,
        tick_value=contract_size,
        volume_min=min_lot,
        volume_max=max_lot,
        volume_step=lot_step,
        stops_level_points=0,
    )
    risk_pct = risk_fraction * 100.0
    if risk_pct <= 2.0:
        return size_for_risk(equity, risk_pct, stop_distance, 0.0, spec).lots
    # Legacy callers may pass up to 10%. The 2% cap is a trading-core gate, not this wrapper's.
    loss_lot = spec.loss_per_lot(stop_distance)
    budget = equity * risk_fraction
    steps = math.floor(budget / loss_lot / spec.volume_step + 1e-9)
    lots = min(steps * spec.volume_step, spec.volume_max)
    if lots < spec.volume_min - 1e-12:
        return 0.0
    return round(lots, 8)
