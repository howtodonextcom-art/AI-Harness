"""Plan-geometry forensics on bars where the v1.1 M15 setup and M5 trigger coincide (BURNED data).

Descriptive only (no outcomes): how large is the stop, how much room is there to the opposing
M15 level, and which part of the v1.1 plan geometry makes RR_TOO_LOW. Reads the funnel dumps for
the timestamps and recomputes the state at those closes.

Usage: ``uv run python scripts/signal_geometry_diag.py data/trade/reports/funnel/v1.1_*.jsonl``
"""

from __future__ import annotations

import json
import statistics
import sys
from datetime import datetime, timedelta
from pathlib import Path

from signal_funnel_dump import BURNED_FROM, BURNED_TO, EQUITY, WARMUP, tail_view

from xau_edge.domain.timeframe import Timeframe
from xau_edge.market_data.ledger import BarLedger
from xau_edge.strategies.edge_program import SERVER_CLOCK
from xau_edge.trading.baseline import BaselineConfig
from xau_edge.trading.decision_core import SnapshotInputs, evaluate
from xau_edge.trading.frames import from_frames
from xau_edge.trading.levels import compute_stop
from xau_edge.trading.live_source import spec_from_broker
from xau_edge.trading.sizing import SymbolSpec


def med(xs: list[float]) -> str:
    return f"{statistics.median(xs):.2f}" if xs else "n/a"


def main() -> None:
    rows = []
    for p in sys.argv[1:]:
        for line in Path(p).read_text(encoding="utf-8").splitlines():
            r = json.loads(line)
            if r["gates"]["m15_setup"] and r["gates"]["m5_trigger"]:
                rows.append(r)
    ledger = BarLedger(Path("data/market"))
    live = json.loads(Path("data/market/live.json").read_text(encoding="utf-8"))
    spec = spec_from_broker(live.get("symbol_spec")) or SymbolSpec()
    cfg = BaselineConfig(allow_unknown_news=True)
    stop_atr, room_atr, atr5_over_atr15, floor_binding, sw_far = [], [], [], 0, 0
    need_atr = []
    cache: dict[str, object] = {}
    for r in rows:
        at = datetime.fromisoformat(r["at"])
        month = at.strftime("%Y-%m")
        if month not in cache:
            lo = max(BURNED_FROM, at.replace(day=1, hour=0, minute=0) - timedelta(days=1))
            hi = min(BURNED_TO, lo + timedelta(days=45))
            cache = {
                month: from_frames(
                    {tf: ledger.load("XAUUSD", tf, lo - w, hi) for tf, w in WARMUP.items()}
                )
            }
        bars = cache[month]
        close = bars.frames[Timeframe.M5].filter(  # type: ignore[attr-defined]
            bars.frames[Timeframe.M5]["available_at"] == at  # type: ignore[attr-defined]
        )
        if close.height == 0:
            continue
        spread, c = float(close["spread"][0]), float(close["close"][0])
        inputs = SnapshotInputs(
            tail_view(bars, at),
            at,
            c,
            c + spread * spec.point,
            spread,
            spec,
            EQUITY,
            "UNKNOWN",
            True,
            True,  # type: ignore[arg-type]
        )
        state, _ = evaluate(inputs, cfg, SERVER_CLOCK)
        direction = 1 if state.h1_trend == "BULLISH" else -1
        atr = state.atr_m15
        if not atr or not state.atr_m5:
            continue
        m5 = state.snapshots.get("M5")
        swing = None if m5 is None else (m5.last_swing_low if direction > 0 else m5.last_swing_high)
        entry = c + (spread * spec.point if direction > 0 else 0.0)
        stop = compute_stop(direction, entry, swing, atr, cfg.levels)
        opposing = state.distance_to_resistance if direction > 0 else state.distance_to_support
        atr5_over_atr15.append(state.atr_m5 / atr)
        if stop is not None:
            stop_atr.append(stop.distance / atr)
            if abs(stop.distance - cfg.levels.atr_k * atr) < 1e-9:
                floor_binding += 1
            if opposing is not None:
                room_atr.append(opposing / atr)
                need_atr.append((cfg.levels.min_net_rr * stop.distance) / atr)
            if swing is not None and abs(entry - swing) > cfg.levels.atr_k * atr:
                sw_far += 1
    print(f"bars analysed: {len(stop_atr)} of {len(rows)} same-bar setup+trigger decisions")
    print(
        f"stop distance / ATR(M15): median {med(stop_atr)} (floor {cfg.levels.atr_k}); floor binding in {floor_binding}"
    )
    print(
        f"room to opposing M15 level / ATR(M15): median {med(room_atr)}; p25 "
        f"{sorted(room_atr)[len(room_atr) // 4]:.2f}"
        if room_atr
        else "no room data"
    )
    print(f"room needed for 1.5 net R / ATR(M15): median {med(need_atr)}")
    print(
        f"share where room < needed: {100 * sum(1 for a, b in zip(room_atr, need_atr, strict=False) if a < b) / max(1, len(room_atr)):.0f}%"
    )
    print(f"ATR(M5)/ATR(M15): median {med(atr5_over_atr15)}")


if __name__ == "__main__":
    main()
