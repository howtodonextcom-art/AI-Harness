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
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.testclient import TestClient

from xau_edge.api.trade import add_trade_routes
from xau_edge.ops.code_version import current_code_version
from xau_edge.trading.acceptance import SCENARIOS, AcceptanceWorld

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
    files["signals_history"] = (
        "GET /trade/signals after the exit",
        http.get("/trade/signals").json(),
    )
    w.close()

    for name, key in (
        ("stale", "stale"),
        ("market_closed", "market_closed"),
        ("paper_corrupt", "paper_corrupt"),
        ("writer_conflict", "writer_conflict"),
        ("expired", "expired"),
    ):
        w = world(name)
        files[key] = (f"GET /trade/decision, scenario {name}", w.engine.view())
        w.close()
    return files


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
