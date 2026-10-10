"""PAPER ACCEPTANCE REPLAY: burned bars through the real TradeEngine + PaperDesk + journal.

Not live and not an edge test. It drives ``TradeEngine.step`` once per M5 close of a burned window
with AUTO_PAPER on (a local setting that only reaches the paper desk), then verifies the lifecycle
(pending -> open -> exit), the journal and the chart marker data. Results are exploratory.

Usage: ``uv run python scripts/trade_acceptance_replay.py --start 2025-12-01 --end 2025-12-29``
"""

from __future__ import annotations

import argparse
import json
import shutil
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import polars as pl

from xau_edge.domain.timeframe import Timeframe
from xau_edge.market_data.calendars import ftmo_calendar
from xau_edge.ops.code_version import current_code_version
from xau_edge.ops.priority import lower_priority
from xau_edge.strategies.edge_program import SERVER_CLOCK
from xau_edge.trading.baseline import BaselineConfig
from xau_edge.trading.engine import EngineConfig, TradeEngine
from xau_edge.trading.paper_desk import DeskConfig, PaperDesk
from xau_edge.trading.replay_source import ReplayMarketSource


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", required=True)
    parser.add_argument("--end", required=True)
    parser.add_argument("--version", default="1.2.0", choices=["1.1.0", "1.2.0", "1.2.1"])
    parser.add_argument("--root", default="data/market")
    parser.add_argument("--out", default="data/trade/acceptance")
    args = parser.parse_args()
    lower_priority()
    start = datetime.fromisoformat(args.start).replace(tzinfo=UTC)
    end = datetime.fromisoformat(args.end).replace(tzinfo=UTC)
    name = f"{args.version}_{args.start}_{args.end}".replace(":", "")  # Windows-safe
    out = Path(args.out) / name
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    source = ReplayMarketSource(args.root, ftmo_calendar(), start, end)
    clock = {"now": start}
    desk = PaperDesk(
        out,
        DeskConfig(),
        code_version=f"replay-{args.version}",
        clock=lambda: clock["now"],
        source_mode=source.SOURCE_MODE,
    )
    engine = TradeEngine(
        source,
        desk,
        EngineConfig(
            root=out,
            baseline=BaselineConfig(version=args.version, allow_unknown_news=True),  # type: ignore[arg-type]
            auto_paper=True,
        ),
        broker_clock=SERVER_CLOCK,
        clock=lambda: clock["now"],
    )
    closes = (
        source.frames[Timeframe.M5]
        .filter((pl.col("available_at") >= start) & (pl.col("available_at") < end))["available_at"]
        .to_list()
    )
    decisions: Counter[str] = Counter()
    for step, at in enumerate(closes, 1):
        if step % 1000 == 0:
            print(
                f"[{args.version} {args.start}] {step}/{len(closes)} steps, {len(desk.trades)} paper trades",
                flush=True,
            )
        clock["now"] = at
        source.set_time(at)
        engine.step(at)
        if engine._signal is not None:
            decisions[engine._signal.decision.value] += 1
    # flush: process remaining bars so an open trade can still exit inside the window
    trades = list(desk.trades.values())
    closed = [t for t in trades if t["status"] == "CLOSED"]
    journal = (
        [
            json.loads(x)
            for x in (out / "paper_journal.jsonl").read_text(encoding="utf-8").splitlines()
            if x.strip()
        ]
        if (out / "paper_journal.jsonl").exists()
        else []
    )
    events: Counter[str] = Counter(j["event"] for j in journal)
    problems: list[str] = []
    for t in trades:
        if t["status"] == "CLOSED":
            for key in (
                "exit_reason",
                "exit_price",
                "net_pnl",
                "mfe_r",
                "mae_r",
                "duration_minutes",
            ):
                if t.get(key) is None:
                    problems.append(f"{t['trade_id']} missing {key}")
            side = 1 if t["side"] == "BUY" else -1
            if (
                side * (t["tp"] - t["fill_price"]) <= 0
                or side * (t["fill_price"] - t["initial_sl"]) <= 0
            ):
                problems.append(f"{t['trade_id']} levels on the wrong side")
        if (
            not any(
                j["event"] == "paper.open" and j.get("trade_id") == t["trade_id"] for j in journal
            )
            and t["status"] != "CANCELLED"
        ):
            problems.append(f"{t['trade_id']} has no paper.open journal line")
    setups = Counter(t["setup_id"] for t in trades)
    report: dict[str, Any] = {
        "mode": "PAPER ACCEPTANCE REPLAY (burned data, not live, not an edge test)",
        "version": args.version,
        "code_version": current_code_version(),
        "window": [args.start, args.end],
        "decisions": dict(decisions),
        "paper_trades": len(trades),
        "closed": len(closed),
        "open_at_end": sum(1 for t in trades if t["status"] == "OPEN"),
        "sides": dict(Counter(t["side"] for t in trades)),
        "exit_reasons": dict(Counter(t.get("exit_reason") for t in closed)),
        "journal_events": dict(events),
        "duplicate_opens_for_one_setup": sum(1 for v in setups.values() if v > 1),
        "problems": problems,
        "exploratory_net_r": round(sum(float(t.get("r_multiple") or 0) for t in closed), 2),
        "exploratory_wins": sum(1 for t in closed if (t.get("net_pnl") or 0) > 0),
        "trades": [
            {k: t.get(k) for k in (
                "trade_id", "side", "status", "opened_at", "closed_at", "fill_price", "initial_sl",
                "tp", "exit_price", "exit_reason", "net_pnl", "r_multiple", "mfe_r", "mae_r",
                "duration_minutes", "setup_id", "lots",
            )}
            for t in trades
        ],
        "note": "exploratory outcomes on burned data; no edge claim",
    }  # fmt: skip
    (out / "report.json").write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k != "trades"}, indent=1, default=str))


if __name__ == "__main__":
    main()
