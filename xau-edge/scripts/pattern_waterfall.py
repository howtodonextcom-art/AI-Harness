"""First-failure waterfall of pattern detections against the 1.5 net R:R research gate. COUNTS ONLY.

    uv run python scripts/pattern_waterfall.py

Reads Development-2 H1 (2011-2018, BURNED, descriptive use only) through the same guarded loader as
``pattern_descriptive.py``. For each detection it asks which gate is the FIRST to fail (order fixed in
``decision_research/waterfall.py``) using only information available at the actionable time:
geometry after adverse tick rounding, nearest opposing confirmed pivot, gross reward-to-risk, whether
a causal executable fill with an evidenced spread exists, and whether the cost ledger is verified.

No price after the detection is read, so no return, hit rate, win rate or expectancy exists here.
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

from xau_edge.decision_research.cost_ledger import default_ledger
from xau_edge.decision_research.fill_model import evidenced_spread_multiplier
from xau_edge.decision_research.rr import CostModel, net_payoff, round_levels_to_tick
from xau_edge.decision_research.structure_room import nearest_barrier_gap, room_ok
from xau_edge.decision_research.waterfall import GateRecord, waterfall
from xau_edge.structure.descriptive_data import (
    ForbiddenDatasetError,
    load_dev2_h1,
    require_descriptive,
)
from xau_edge.structure.detection import PatternDetection
from xau_edge.structure.pivots import Pivot, confirmed_pivots
from xau_edge.structure.reversal import detect_reversals
from xau_edge.structure.wolfe import detect_wolfe_patterns

ROOT = Path(__file__).resolve().parents[1]
HISTORY = ROOT / "data" / "research_history"
OUT = ROOT / "docs" / "reports" / "data"
TICK = 0.01
PIVOT_SIDE = 3  # the detectors' own default (left = right = 3); the same pivots they confirm on
ZERO = CostModel(
    spread=0.0, slippage=0.0, commission=0.0, swap=0.0, source="gross geometry only", verified=False
)


def levels(d: PatternDetection) -> tuple[float, float, float] | None:
    ref = d.reference_levels
    entry = ref.get("entry_reference")
    stop = ref.get("invalidation_reference", ref.get("stop_reference"))
    target = ref.get("measured_move_reference", ref.get("target_reference"))
    if entry is None or stop is None or target is None:
        return None
    return float(entry), float(stop), float(target)


def record(
    family: str, d: PatternDetection, pivots: list[Pivot], year: int, cost_verified: bool
) -> tuple[GateRecord, bool]:
    side = "BUY" if d.bias == "LONG" else "SELL"
    raw = levels(d)
    no_barrier = False
    gross: float | None = None
    valid = False
    room: bool | None = None
    if raw is not None:
        entry, stop, target = round_levels_to_tick(side, *raw, TICK)  # type: ignore[arg-type]
        payoff = net_payoff(side, entry, stop, target, ZERO)  # type: ignore[arg-type]
        if payoff is not None:
            valid, gross = True, payoff.gross_rr
            gap = nearest_barrier_gap(side, entry, pivots, d.actionable_at)  # type: ignore[arg-type]
            room, no_barrier = room_ok(gap, payoff.gross_reward, TICK), gap is None
    return (
        GateRecord(
            family=family,
            pattern_id=d.pattern_id,
            valid_geometry=valid,
            room_ok=room,
            gross_rr=gross,
            fill_verified=evidenced_spread_multiplier(year) is not None,
            cost_verified=cost_verified,
        ),
        no_barrier,
    )


def main() -> int:
    try:
        policy = require_descriptive("dev2_h1")
    except ForbiddenDatasetError as exc:
        print(f"REFUSED: {exc}")
        return 2
    files = sorted((HISTORY / "XAUUSD" / "H1").glob("*.parquet"))
    if len(files) != 1:
        print(f"REFUSED: expected exactly one H1 history file, found {len(files)}")
        return 2
    frame = load_dev2_h1(files[0])
    h, lo, c = (frame[col].to_numpy().astype(np.float64) for col in ("high", "low", "close"))
    stamps = frame["timestamp"].to_list()
    pivots = confirmed_pivots(h, lo, c, left=PIVOT_SIDE, right=PIVOT_SIDE)
    now = datetime.now(UTC)
    ledger = default_ledger(2025, "LONDON", "BUY", 1, now)
    cost_verified = ledger.gate_cost_model(now) is not None
    families = {
        "wolfe": detect_wolfe_patterns(h, lo, c),
        "double_top_bottom": detect_reversals(h, lo, c, kinds=("DOUBLE",)),
        "head_and_shoulders": detect_reversals(h, lo, c, kinds=("HNS",)),
    }
    records: list[GateRecord] = []
    no_barrier = 0
    for family, found in families.items():
        for d in found:
            rec, nb = record(family, d, pivots, stamps[d.actionable_at].year, cost_verified)
            records.append(rec)
            no_barrier += int(nb)
    report = {
        "dataset": "dev2_h1",
        "classification": policy.classification,
        "bars": int(frame.height),
        "outcome_analysis": "NONE",
        "gate": {
            "min_net_rr": 1.5,
            "tick": TICK,
            "pivots": f"left=right={PIVOT_SIDE}, confirmed_at <= actionable_at",
        },
        "cost_ledger_blockers": [list(b) for b in ledger.blockers(now)],
        "no_barrier_known": no_barrier,
        "waterfall": waterfall(records),
    }
    OUT.mkdir(parents=True, exist_ok=True)
    target = OUT / "pattern_waterfall_dev2_h1.json"
    target.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(report["waterfall"], indent=2))  # type: ignore[arg-type]
    print(f"cost ledger blockers: {report['cost_ledger_blockers']}")
    print(f"written: {target}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
