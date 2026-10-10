"""Serve the Trading Desk API over an ACCEPTANCE REPLAY world (burned bars, a replay clock).

Usage: ``uv run python scripts/serve_acceptance.py [--port 8100] [--scenario buy_tp]``

It mounts the SAME ``/trade/*`` routes as production over the SAME ``build_trade_engine`` wiring,
but the market source is ``ReplayMarketSource`` (burned FTMO bars) and the clock is the replay
clock, so everything it serves is labelled ACCEPTANCE_REPLAY and can never be mistaken for LIVE.
It exists to test the product end to end (browser included). It never touches MT5, never writes
into ``data/trade``, and ``/acceptance/*`` is a test control surface that only exists here.

    GET  /acceptance/scenarios       the registry
    POST /acceptance/load/{name}     rebuild a fresh world at that scenario's moment
    POST /acceptance/advance?minutes=N   replay N more minutes (one M5 close at a time)
    GET  /acceptance/state           scenario, replay clock, hero state
"""

from __future__ import annotations

import argparse
import tempfile
from pathlib import Path
from typing import Any, cast

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from xau_edge.api.trade import add_trade_routes
from xau_edge.trading.acceptance import SCENARIOS, AcceptanceWorld
from xau_edge.trading.engine import TradeEngine


class _Current:
    """Delegates to the engine of whichever world is loaded (routes bind this object once)."""

    def __init__(self) -> None:
        self.world: AcceptanceWorld | None = None

    def __getattr__(self, name: str) -> Any:
        if self.world is None:
            raise HTTPException(status_code=503, detail="no acceptance scenario loaded")
        return getattr(self.world.engine, name)


def build_app(market_root: Path, out_root: Path, port: int, first: str | None) -> FastAPI:
    app = FastAPI(title="XAU EDGE trading desk - ACCEPTANCE REPLAY (not live)")
    origins = ("http://localhost:3000", "http://127.0.0.1:3000")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[*origins, "http://127.0.0.1:3200"],
        allow_methods=["GET"],
    )
    current = _Current()

    def load(name: str) -> AcceptanceWorld:
        if name not in SCENARIOS:
            raise HTTPException(status_code=404, detail=f"unknown scenario {name!r}")
        if current.world is not None:
            current.world.close()
            current.world = None
        current.world = AcceptanceWorld(market_root, out_root, SCENARIOS[name])
        return current.world

    add_trade_routes(app, cast(TradeEngine, current), port=port, allowed_origins=origins)

    @app.get("/md/{sym}/bars")
    def bars(
        sym: str, timeframe: str = "M5", limit: int = 400, include_forming: bool = False
    ) -> dict[str, Any]:
        if current.world is None:
            raise HTTPException(status_code=503, detail="no acceptance scenario loaded")
        return current.world.bars(timeframe, min(limit, 1000))

    @app.get("/acceptance/scenarios")
    def scenarios() -> dict[str, Any]:
        return {
            n: {"description": s.description, "version": s.version, "moment": s.moment.isoformat()}
            for n, s in SCENARIOS.items()
        }

    @app.post("/acceptance/load/{name}")
    def load_route(name: str) -> dict[str, Any]:
        world = load(name)
        return {"loaded": name, "replay_now": world.now.isoformat()}

    @app.post("/acceptance/advance")
    def advance(minutes: int = 5) -> dict[str, Any]:
        if current.world is None:
            raise HTTPException(status_code=503, detail="no acceptance scenario loaded")
        steps = current.world.advance_minutes(minutes)
        return {"replay_now": current.world.now.isoformat(), "m5_closes": steps}

    @app.get("/acceptance/state")
    def state() -> dict[str, Any]:
        if current.world is None:
            return {"loaded": None}
        view = current.world.engine.view()
        return {
            "loaded": current.world.scenario.name,
            "replay_now": current.world.now.isoformat(),
            "hero": view["hero"]["state"],
            "source_mode": view["source_mode"],
        }

    if first:
        load(first)
    return app


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8100)
    parser.add_argument("--market-root", default="data/market")
    parser.add_argument("--scenario", default=None)
    parser.add_argument("--out", default=None, help="working directory (default: a temp dir)")
    args = parser.parse_args()
    out = Path(args.out) if args.out else Path(tempfile.mkdtemp(prefix="xau-acceptance-"))
    out.mkdir(parents=True, exist_ok=True)
    app = build_app(Path(args.market_root), out, args.port, args.scenario)
    uvicorn.run(app, host="127.0.0.1", port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
