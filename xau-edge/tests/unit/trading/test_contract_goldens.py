"""Backend <-> frontend contract: the goldens are real serializations and must track the code.

``apps/dashboard/e2e/fixtures/golden/*.json`` are written by ``scripts/generate_trade_goldens.py``
from the real ``TradeEngine``/``PaperDesk`` (an acceptance replay of burned bars). The dashboard
type-checks them against ``lib/trade.ts``; this test checks them against what the backend
serializes TODAY. A field the backend renames, adds or drops breaks one of the two, so a mismatch
like ``initial_tp`` (UI) vs ``tp`` (desk) cannot survive CI again.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from tests.unit.api.test_api_trade import HEADERS, ORIGIN  # noqa: F401 - shared constants
from tests.unit.market_data.test_collector_ledger import FakeClient, make_collector
from xau_edge.api.trade import add_trade_routes
from xau_edge.market_data.validators.market_calendar import MarketCalendar
from xau_edge.strategies.edge_program import SERVER_CLOCK
from xau_edge.trading.baseline import BaselineConfig
from xau_edge.trading.engine import EngineConfig, TradeEngine
from xau_edge.trading.live_source import LiveTradingMarketSource
from xau_edge.trading.paper_desk import PaperDesk

ROOT = Path(__file__).resolve().parents[3]
GOLDEN = ROOT / "apps" / "dashboard" / "e2e" / "fixtures" / "golden"
MARKET = ROOT / "data" / "market"

# Fields that exist only in some states (the view omits them when there is nothing to say).
OPTIONAL = {"served_at", "take_profit_2", "equity_used", "equity_source", "strategy_version"}


# Maps keyed by data (reason codes, counts per outcome): their keys are values, not structure.
FREE_MAPS = {"counts", "refusals", "exit_reasons", "setup_phases", "structure", "market", "today"}


def shape_diff(golden: Any, live: Any, path: str = "$") -> list[str]:
    """Differences in dict keys at every path both sides have (None / empty lists are skipped)."""
    if isinstance(golden, dict) and isinstance(live, dict):
        if path.rsplit(".", 1)[-1] in FREE_MAPS:
            return []
        out = [
            f"{path}.{k}: only in {'golden' if k in golden else 'backend'}"
            for k in sorted(set(golden) ^ set(live))
            if k not in OPTIONAL
        ]
        for key in sorted(set(golden) & set(live)):
            out += shape_diff(golden[key], live[key], f"{path}.{key}")
        return out
    if isinstance(golden, list) and isinstance(live, list) and golden and live:
        return shape_diff(golden[0], live[0], f"{path}[]")
    return []


def golden(name: str) -> Any:
    return json.loads((GOLDEN / f"{name}.json").read_text(encoding="utf-8"))


@pytest.fixture
def http(tmp_path: Path) -> TestClient:
    client = FakeClient()
    make_collector(tmp_path / "market", client).run_once()
    engine = TradeEngine(
        LiveTradingMarketSource(tmp_path / "market", MarketCalendar()),
        PaperDesk(tmp_path / "trade", clock=lambda: client.now),
        EngineConfig(root=tmp_path / "trade", baseline=BaselineConfig(allow_unknown_news=True)),
        broker_clock=SERVER_CLOCK,
        clock=lambda: client.now,
    )
    app = FastAPI()
    add_trade_routes(app, engine, port=8000, allowed_origins=(ORIGIN,))
    return TestClient(app, base_url="http://127.0.0.1:8000")


def test_goldens_exist_and_are_marked_as_replay() -> None:
    index = json.loads((GOLDEN / "index.json").read_text(encoding="utf-8"))
    assert "NOT LIVE" in index["provenance"]
    for name in ("wait", "buy", "sell", "open_paper", "closed_paper", "journal_closed"):
        assert (GOLDEN / f"{name}.json").exists(), name
    for name in ("wait", "buy", "sell", "open_paper", "closed_paper"):
        assert golden(name)["source_mode"] == "ACCEPTANCE_REPLAY"


def test_goldens_cover_the_states_the_owner_must_see() -> None:
    assert golden("wait")["hero"]["state"] == "WAIT"
    assert golden("buy")["hero"]["state"] == "BUY_READY"
    assert golden("sell")["hero"]["state"] == "SELL_READY"
    assert golden("open_paper")["hero"]["state"] == "POSITION_OPEN"
    assert golden("closed_paper")["hero"]["state"] == "EXITED"
    assert golden("journal_closed")["trades"][0]["status"] == "CLOSED"


def test_decision_view_keeps_the_shape_the_dashboard_types_describe(http: TestClient) -> None:
    view = http.get("/trade/decision").json()
    wait = golden("wait")
    for name in ("wait", "buy", "sell", "open_paper", "closed_paper"):
        # only the state-dependent parts may differ at the top level
        differing = set(golden(name)) ^ set(view)
        assert differing <= {"decision", "trade_plan", "entry_blockers"} | OPTIONAL, (
            name,
            differing,
        )
    assert shape_diff(wait["hero"], view["hero"]) == []
    assert shape_diff(wait["status_strip"], view["status_strip"]) == []
    assert shape_diff(wait["forward_acceptance"], view["forward_acceptance"]) == []
    assert shape_diff(wait["strategy"], view["strategy"]) == []
    assert shape_diff(wait["evidence"], view["evidence"]) == []
    assert shape_diff(wait["demo"], view["demo"]) == []


def test_markers_and_journal_shapes(http: TestClient) -> None:
    journal = http.get("/trade/journal").json()
    expected = golden("journal_closed")
    assert set(journal) == set(expected)
    markers = http.get("/trade/markers").json()
    assert {"simulated", "source_mode", "signals", "paper_trades"} <= set(markers)


@pytest.mark.skipif(not MARKET.exists(), reason="burned market data is not in this checkout")
def test_goldens_are_what_the_real_engine_serializes_today(tmp_path: Path) -> None:
    spec = importlib.util.spec_from_file_location(
        "generate_trade_goldens", ROOT / "scripts" / "generate_trade_goldens.py"
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    collect = module.collect
    fresh = collect(MARKET, tmp_path)
    for name, (_what, payload) in fresh.items():
        again = json.loads(json.dumps(payload, sort_keys=True, default=str))
        assert shape_diff(golden(name), again) == [], name
        if name != "signals":
            assert (
                golden(name)["source_mode" if "source_mode" in again else "simulated"]
                == (again["source_mode" if "source_mode" in again else "simulated"])
            )
