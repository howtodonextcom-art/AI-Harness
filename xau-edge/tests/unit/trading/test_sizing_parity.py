"""One sizing authority: same inputs → same lots on the canonical and legacy wrappers."""

from __future__ import annotations

from xau_edge.risk.sizing import position_size
from xau_edge.trading.sizing import SymbolSpec, size_for_risk


def test_same_equity_risk_entry_sl_and_spec_give_the_same_lots() -> None:
    equity = 100_000.0
    risk_pct = 0.25
    entry = 2650.30
    sl = 2645.30
    spec = SymbolSpec(
        tick_size=0.01,
        tick_value=1.0,
        contract_size=100.0,
        volume_min=0.01,
        volume_max=100.0,
        volume_step=0.01,
    )
    canonical = size_for_risk(equity, risk_pct, entry, sl, spec)
    # loss_per_lot = distance / 0.01 * 1 = distance * 100 == distance * contract_size
    legacy = position_size(
        equity,
        risk_pct / 100.0,
        abs(entry - sl),
        contract_size=spec.contract_size,
        min_lot=spec.volume_min,
        lot_step=spec.volume_step,
        max_lot=spec.volume_max,
    )
    assert canonical.lots == legacy
    assert canonical.lots > 0
