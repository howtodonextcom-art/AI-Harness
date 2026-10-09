"""Replay smoke test of the trading desk on BURNED development data (never Test-H or the holdout).

For every M5 close in the window it computes the decision TWO ways and compares them:

* ``full``  : all history closed at that time (what a research replay sees);
* ``live``  : the same history cut to the tail windows the live source reads (what the desk sees).

Any difference is a parity blocker. It then feeds the BUY/SELL decisions to the paper desk (open,
monitor on M1 bars, auto exit) to prove the lifecycle end to end. The numbers are a SANITY check of
the pipeline (frequency, plan validity, refusal mix, lifecycle), NOT evidence of an edge, and are
never used to tune a parameter.

Usage: ``uv run python scripts/trade_replay_smoke.py [--start 2025-11-03] [--end 2025-12-01]``
"""

from __future__ import annotations

import argparse
import json
import tempfile
import time
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import polars as pl

from xau_edge.domain.timeframe import Timeframe
from xau_edge.market_data.ledger import BarLedger
from xau_edge.strategies.edge_program import SERVER_CLOCK
from xau_edge.trading.baseline import BaselineConfig
from xau_edge.trading.decision_core import SnapshotInputs, comparable, evaluate
from xau_edge.trading.frames import MultiTfBars, from_frames
from xau_edge.trading.live_source import TAILS, spec_from_broker
from xau_edge.trading.paper_desk import DeskRefusal, PaperDesk
from xau_edge.trading.schema import TradeDecision
from xau_edge.trading.sizing import SymbolSpec

BURNED_FROM = datetime(2025, 5, 1, tzinfo=UTC)
BURNED_TO = datetime(2026, 5, 1, tzinfo=UTC)
WARMUP = {
    Timeframe.M1: timedelta(days=4),
    Timeframe.M5: timedelta(days=10),
    Timeframe.M15: timedelta(days=20),
    Timeframe.M30: timedelta(days=30),
    Timeframe.H1: timedelta(days=60),
    Timeframe.H4: timedelta(days=200),
}
EQUITY = 10_000.0


@dataclass(frozen=True)
class Quote:
    bid: float
    ask: float
    spread_points: float
    stale: bool = False


def _day(text: str) -> datetime:
    return datetime.fromisoformat(text).replace(tzinfo=UTC)


def _tail_view(bars: MultiTfBars, at: datetime) -> MultiTfBars:
    closed = bars.truncated(at)
    return MultiTfBars({tf: df.tail(TAILS[tf]) for tf, df in closed.frames.items()})


def _plan_problems(signal: Any, spec: SymbolSpec) -> list[str]:
    """Structural invariants of every actionable plan (a violation is a bug, not a result)."""
    out: list[str] = []
    side = 1 if signal.decision is TradeDecision.BUY else -1
    e, sl, tp = signal.entry_price, signal.stop_loss, signal.take_profit
    if None in (e, sl, tp, signal.position_size, signal.risk_reward, signal.signal_expiry):
        return ["INCOMPLETE_PLAN"]
    if not (side * (e - sl) > 0 and side * (tp - e) > 0):
        out.append("LEVELS_ON_WRONG_SIDE")
    if abs(e - sl) < spec.stops_level_points * spec.point:
        out.append("STOP_INSIDE_BROKER_MINIMUM")
    if signal.position_size < spec.volume_min:
        out.append("LOT_BELOW_MINIMUM")
    step = spec.volume_step
    if abs(signal.position_size / step - round(signal.position_size / step)) > 1e-6:
        out.append("LOT_NOT_ON_STEP")
    if signal.risk_amount is not None and signal.risk_amount > EQUITY * 0.005 + 1e-6:
        out.append("RISK_ABOVE_CAP")
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", default="2025-11-03")
    parser.add_argument("--end", default="2025-12-01")
    parser.add_argument("--root", default="data/market")
    parser.add_argument("--out", default="data/trade/reports/replay_smoke.json")
    parser.add_argument("--skip-parity", action="store_true", help="faster: no live-tail pass")
    args = parser.parse_args()
    start, end = _day(args.start), _day(args.end)
    if start < BURNED_FROM or end > BURNED_TO:
        msg = "refused: the window must lie inside the burned period 2025-05-01..2026-04-30"
        raise SystemExit(msg)

    ledger = BarLedger(Path(args.root))
    frames = {
        tf: ledger.load("XAUUSD", tf, start - WARMUP[tf], end + timedelta(days=1)) for tf in WARMUP
    }
    bars = from_frames(frames)
    live = json.loads((Path(args.root) / "live.json").read_text(encoding="utf-8"))
    spec = spec_from_broker(live.get("symbol_spec")) or SymbolSpec()
    cfg = BaselineConfig(allow_unknown_news=True)
    m5 = bars.frames[Timeframe.M5]
    times = m5.filter((pl.col("available_at") >= start) & (pl.col("available_at") < end))[
        "available_at"
    ].to_list()

    desk = PaperDesk(Path(tempfile.mkdtemp()), clock=lambda: start)
    m1 = bars.frames[Timeframe.M1]
    counts: Counter[str] = Counter()
    refusals: Counter[str] = Counter()
    sole: Counter[str] = Counter()
    h1_directional = 0
    problems: Counter[str] = Counter()
    mismatches: list[dict[str, Any]] = []
    setups: set[str] = set()
    desk_refusals: Counter[str] = Counter()
    previous = times[0]
    desk.last_bar = previous - timedelta(minutes=1)
    t0 = time.perf_counter()
    for at in times:
        spread = float(m5.filter(pl.col("available_at") == at)["spread"][0])
        close = float(m5.filter(pl.col("available_at") == at)["close"][0])
        bid, ask = close, close + spread * spec.point

        full_in = SnapshotInputs(
            bars.truncated(at), at, bid, ask, spread, spec, EQUITY, "UNKNOWN", True, True
        )
        tail_in = SnapshotInputs(
            _tail_view(bars, at), at, bid, ask, spread, spec, EQUITY, "UNKNOWN", True, True
        )
        state_full, full = evaluate(full_in, cfg, SERVER_CLOCK)
        tail = full if args.skip_parity else evaluate(tail_in, cfg, SERVER_CLOCK)[1]
        if comparable(full) != comparable(tail):
            mismatches.append(
                {"at": at.isoformat(), "full": comparable(full), "live": comparable(tail)}
            )
        counts[full.decision.value] += 1
        if len(full.refusal_reasons) == 1:
            sole[full.refusal_reasons[0].value] += 1
        if full.h1_bias in ("BULLISH", "BEARISH"):
            h1_directional += 1
        refusals.update(r.value for r in full.refusal_reasons)
        # the desk: monitor what happened since the last decision, then maybe take this one
        new = m1.filter((pl.col("timestamp") > desk.last_bar) & (pl.col("available_at") <= at))
        m5s = state_full.snapshots.get("M5")
        desk.process_bars(
            new.select("timestamp", "open", "high", "low", "close", "spread"),
            atr=state_full.atr_m5,
            swing_low=None if m5s is None else m5s.last_swing_low,
            swing_high=None if m5s is None else m5s.last_swing_high,
            invalidated={
                "BUY": state_full.h1_trend == "BEARISH",
                "SELL": state_full.h1_trend == "BULLISH",
            },
        )
        if full.decision is not TradeDecision.WAIT:
            setups.add(full.setup_id)
            for p in _plan_problems(full, spec):
                problems[p] += 1
            quote = Quote(bid, ask, spread)
            if not desk.can_open(at, state_full.session, 0.25, quote):
                try:
                    desk.open_from_decision(
                        full, risk_pct=0.25, quote=quote, spec=spec, now=at, market={}
                    )
                except DeskRefusal as exc:
                    desk_refusals[exc.code] += 1
        previous = at
    elapsed = time.perf_counter() - t0
    closed = desk.closed_trades()
    done = [t for t in closed if t["status"] == "CLOSED"]
    exits = Counter(t.get("exit_reason") for t in done)
    report = {
        "window": [args.start, args.end],
        "burned_period_only": True,
        "decisions": len(times),
        "counts": dict(counts),
        "distinct_setups": len(setups),
        "top_refusals": refusals.most_common(10),
        "decisions_with_exactly_one_blocker": sole.most_common(10),
        "decisions_with_h1_direction": h1_directional,
        "plan_invariant_violations": dict(problems),
        "parity_mismatches": len(mismatches),
        "parity_examples": mismatches[:3],
        "paper_trades_closed": len(done),
        "paper_trades_open_at_end": int(desk.open_trade() is not None),
        "paper_exit_reasons": dict(exits),
        "desk_refusals": dict(desk_refusals),
        "paper_net_r_sanity": round(sum(float(t.get("r_multiple") or 0) for t in done), 2),
        "seconds": round(elapsed, 1),
        "ms_per_decision": round(1000 * elapsed / max(1, len(times)), 1),
        "note": "sanity check of the pipeline only; not evidence of an edge",
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    if mismatches or problems:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
