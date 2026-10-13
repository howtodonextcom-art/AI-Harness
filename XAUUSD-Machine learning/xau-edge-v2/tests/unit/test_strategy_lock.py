"""The deterministic strategy is LOCKED: G9 (human layer) and G10 (M1 execution intelligence) are
advisory layers around it and must not change one byte of it.

These pins were taken from the files as they stood at the end of G8.1, which the golden parity
(1.8M+ checks against V1, ``tests/golden``) proves equal to V1's baseline v1.1.0. A change to any
of these files fails this test; changing the strategy is a separate, owner-approved piece of work
(new ADR, new golden run, new pins), never a side effect of a UI or advisory change.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

CORE = Path(__file__).resolve().parents[2] / "src" / "xau_edge_v2" / "core"

PINS = {
    "decision.py": "7fc063908e97cf790d7210150b9c1fba777e86b9b37cf025db90e7e3dbf23371",
    "risk.py": "9c4015fc07f5c70754deae62e35ee26a8ca4dbc1823fb8d352fd91b56b918316",
    "market_state.py": "71400a56aa35d2084bf3b1ab40e818017ca080f3cd1d9c800bfac03b94eaac31",
    "structure.py": "852d6528148b1efd6bd34169a2544dc30a87caf108fe403985415af6743bb0bd",
    "indicators.py": "c58a43db40cddd3fa55e91c8c56170e83a3d3395ec7af84135ac3bc54aa685c4",
    "frames.py": "4a26435e79bf7e5c8d3c828f347ca35d5d2711ac0a0d05723d67d0b9cc45b9e4",
    "costs.py": "dccca7dbad3f5f907dd32cc1f64bb886163ce9ef536f51682cbf4b5bb5616837",
}


def digest(name: str) -> str:
    return hashlib.sha256((CORE / name).read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def test_the_strategy_files_are_byte_identical_to_the_g8_1_state() -> None:
    changed = {n: digest(n) for n, pinned in PINS.items() if digest(n) != pinned}
    assert not changed, f"strategy files changed: {sorted(changed)}"


def test_the_strategy_constants_are_the_ones_v1_used() -> None:
    from xau_edge_v2.core import market_state as ms  # noqa: PLC0415
    from xau_edge_v2.core import risk  # noqa: PLC0415
    from xau_edge_v2.core.decision import DecisionConfig  # noqa: PLC0415

    assert (risk.ATR_K, risk.MAX_STOP_ATR, risk.R_MULTIPLE, risk.MIN_NET_RR) == (
        1.25,
        3.0,
        2.0,
        1.5,
    )
    assert (ms.WIDE_SPREAD_PERCENTILE, ms.MAX_SPREAD_TO_ATR) == (0.9, 0.15)
    cfg = DecisionConfig()
    assert (cfg.risk_pct, cfg.min_clear_atr, cfg.expiry_bars_m5) == (0.25, 1.0, 3)
    assert cfg.block_high_volatility and cfg.block_low_volatility and cfg.block_quiet_m1
