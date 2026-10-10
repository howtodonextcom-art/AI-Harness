"""Write the frontend contract goldens from REAL backend objects (no hand-written JSON).

Every file under ``apps/dashboard/e2e/fixtures/golden/`` is the serialization produced by
``TradeEngine`` / ``PaperDesk`` over burned FTMO bars (an acceptance replay, labelled
ACCEPTANCE_REPLAY, never LIVE). ``index.json`` records the provenance of each file. The dashboard
type-checks the files against ``lib/trade.ts`` and a backend test compares their key structure with
what the code serializes today, so a renamed or dropped field breaks CI (the ``initial_tp`` vs
``tp`` class of bug).

Usage: ``uv run python scripts/generate_trade_goldens.py``
"""

from __future__ import annotations

import json
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.testclient import TestClient

from xau_edge.api.trade import add_trade_routes
from xau_edge.ops.code_version import current_code_version
from xau_edge.trading.acceptance import SCENARIOS, AcceptanceWorld
from xau_edge.trading.coverage import decision_coverage

OUT = Path("apps/dashboard/e2e/fixtures/golden")
PORT = 8100


def collect(market: Path, out_root: Path) -> dict[str, tuple[str, Any]]:
    """name -> (what it is, payload). Shared with the contract test."""
    files: dict[str, tuple[str, Any]] = {}

    def world(name: str) -> AcceptanceWorld:
        return AcceptanceWorld(market, out_root, SCENARIOS[name])

    w = world("wait")
    files["wait"] = ("GET /trade/decision, ordinary WAIT", w.engine.view())
    w.close()

    w = world("sell_ready")
    files["sell"] = ("GET /trade/decision, real SELL setup", w.engine.view())
    w.close()

    w = world("buy_tp")
    files["buy"] = ("GET /trade/decision, real BUY setup", w.engine.view())
    setup = w.engine.view()["decision"]["setup_id"]
    w.engine.paper_open(setup_id=setup, risk_pct=0.25)
    w.advance_minutes(10)
    files["open_paper"] = ("GET /trade/decision, BUY paper position OPEN", w.engine.view())
    w.advance_minutes(50)
    files["closed_paper"] = ("GET /trade/decision, BUY paper trade exited", w.engine.view())
    files["journal_closed"] = (
        "GET /trade/journal after the exit",
        {
            "simulated": True,
            "source_mode": w.engine.source_mode,
            "desk_fault": w.engine.desk.load_error or w.engine.desk.integrity_error,
            "open": w.engine.desk.open_trade(),
            "trades": w.engine.desk.closed_trades(),
            "evidence": w.engine.evidence(),
        },
    )
    files["signals"] = (
        "signal log records of the replay day",
        w.engine.telemetry.read_signals(w.engine.now()),
    )
    # the real route handlers, called as the dashboard calls them
    app = FastAPI()
    add_trade_routes(app, w.engine, port=PORT, allowed_origins=("http://localhost:3000",))
    http = TestClient(app, base_url=f"http://127.0.0.1:{PORT}")
    files["markers_closed"] = (
        "GET /trade/markers after the exit",
        http.get("/trade/markers").json(),
    )
    files["setups_history"] = ("GET /trade/setups after the exit", http.get("/trade/setups").json())
    files["signals_history"] = (
        "GET /trade/signals after the exit",
        http.get("/trade/signals").json(),
    )
    w.close()

    # the other two ways a paper trade ends (TAKE_PROFIT is `closed_paper` above): the stop and the clock
    for name, key, reason in (
        ("sell_ready", "closed_sl", "STOP_LOSS"),
        ("buy_time", "closed_time", "TIME_EXIT"),
    ):
        w = world(name)
        setup = w.engine.view()["decision"]["setup_id"]
        w.engine.paper_open(setup_id=setup, risk_pct=0.25)
        for _ in range(120):  # at most 20 hours of replay, ten minutes at a time
            w.advance_minutes(10)
            if w.engine.desk.open_trade() is None:
                break
        view = w.engine.view()
        if view["hero"]["action"]["code"] != "EXIT":
            raise SystemExit(f"{name} did not exit")
        if view["desk"]["last_exit"]["exit_reason"] != reason:
            raise SystemExit(f"{name} exited another way than {reason}")
        files[key] = (f"GET /trade/decision, paper trade exited by {reason}", view)
        w.close()

    for name, key in (
        ("stale", "stale"),
        ("market_closed", "market_closed"),
        ("paper_corrupt", "paper_corrupt"),
        ("writer_conflict", "writer_conflict"),
        ("expired", "expired"),
        ("buy_watch", "buy_watch"),
        ("buy_armed", "buy_armed"),
        ("sell_watch", "sell_watch"),
        ("sell_armed", "sell_armed"),
        ("sell_invalidated", "sell_invalidated"),
    ):
        w = world(name)
        files[key] = (f"GET /trade/decision, scenario {name}", w.engine.view())
        w.close()
    files["coverage_incomplete"] = ("decision_coverage() over a restart gap", incomplete_coverage())
    return files


def incomplete_coverage() -> dict[str, Any]:
    """The real ``decision_coverage`` for the 2026-10-09 pattern: two runs of ~1 row/min and a restart gap."""
    start = datetime(2026, 10, 9, 12, 53, tzinfo=UTC)
    bars = [start + timedelta(minutes=i) for i in range(240)]
    kept = [i for i in range(240) if i < 110 or 141 <= i < 200]
    rows = [
        {"at": (bars[i] + timedelta(minutes=1, seconds=4)).isoformat(), "m1_bar": bars[i].isoformat(),
         "run": "a1b2c3d4" if i < 110 else "e5f6a7b8"}
        for i in kept
    ]  # fmt: skip
    return decision_coverage(
        bars, rows, window_from=start, window_to=start + timedelta(minutes=240)
    )


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix="xau-goldens-"))
    index: dict[str, Any] = {
        "provenance": "ACCEPTANCE_REPLAY of burned FTMO bars through the real TradeEngine; NOT LIVE",
        "code_version": current_code_version(),
        "files": {},
    }
    for name, (what, payload) in collect(Path("data/market"), work).items():
        (OUT / f"{name}.json").write_text(
            json.dumps(payload, indent=1, sort_keys=True, default=str) + "\n", encoding="utf-8"
        )
        index["files"][f"{name}.json"] = what
    (OUT / "index.json").write_text(json.dumps(index, indent=1) + "\n", encoding="utf-8")
    print(f"wrote {len(index['files'])} goldens to {OUT}")


if __name__ == "__main__":
    main()
