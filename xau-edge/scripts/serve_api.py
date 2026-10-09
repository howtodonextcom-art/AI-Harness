"""Serve the research API on localhost (never exposed beyond 127.0.0.1).

Usage: ``uv run python scripts/serve_api.py [--port 8000]``
The research endpoints are read-only; live trading does not exist in this project.

With ``XAU_EDGE_WEB_CONTROL=true`` (default false) the local web control plane ``/control/*`` is
mounted too (ADR-0023): start/stop the bot, DRY_RUN/DEMO, smoke and flatten, guarded by a token
that is generated at every start and written to ``data/execution/control_token`` (readable by the
current user only). The bot itself needs the MT5 package, so start the API with both extras:
``uv run --extra api --extra mt5 python scripts/serve_api.py``.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import uvicorn

from xau_edge.api.app import create_app
from xau_edge.api.bot import BotContext
from xau_edge.api.service import ApiContext
from xau_edge.backtest.costs import CostModel
from xau_edge.config import Settings
from xau_edge.domain.timeframe import Timeframe
from xau_edge.execution.paper import PaperExecutionBroker
from xau_edge.execution.safety import ExecutionSafety, assert_live_trading_disabled
from xau_edge.execution.trader import PaperTrader
from xau_edge.experiments.registry import ExperimentRegistry
from xau_edge.market_data.catalog import DatasetCatalog
from xau_edge.observability import configure_logging
from xau_edge.research.service import ResearchService
from xau_edge.risk.engine import RiskEngine, RiskLimits
from xau_edge.risk.prop_rules import load_prop_profile
from xau_edge.signals.engine import MarketFrames

DEFAULT_TERMINAL = r"C:\Program Files\FTMO Global Markets MT5 Terminal\terminal64.exe"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default="data/raw")
    parser.add_argument("--prop", default="configs/prop/ftmo_2step.yaml")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--terminal-path", default=DEFAULT_TERMINAL)
    args = parser.parse_args()
    configure_logging("INFO")

    catalog = DatasetCatalog(args.root)

    def load() -> MarketFrames:
        return MarketFrames(
            *(
                catalog.load("XAUUSD", tf).frame
                for tf in (Timeframe.M5, Timeframe.M15, Timeframe.H1, Timeframe.H4)
            )
        )

    assert_live_trading_disabled()
    settings = Settings()
    prop = load_prop_profile(Path(args.prop))
    journal = Path("data/paper/forward-journal.jsonl")
    broker = PaperExecutionBroker(100_000.0, costs=CostModel(), journal_path=journal)
    paper = PaperTrader(broker, RiskEngine(RiskLimits(), prop), ExecutionSafety())
    control = None
    if settings.web_control:
        from xau_edge.control.factory import build_control_service  # noqa: PLC0415 - opt-in

        control = build_control_service(
            repo_root=Path.cwd(),
            terminal_path=args.terminal_path,
            data_dir=Path.cwd() / settings.data_dir,
        )
        print("Web control plane ON (/control/*); token written for the dashboard server.")
    ctx = ApiContext(
        load_frames=load,
        registry=ExperimentRegistry("experiments/runs"),
        prop=prop,
        models_dir=Path("models"),
        paper=paper,
        research=ResearchService(Path(__file__).resolve().parents[1]),
        bot=BotContext(
            state_path=settings.execution_state_path,
            status_path=Path("data/execution/status.json"),
            cycles_path=Path("data/execution")
            / ("funded_cycles.jsonl" if settings.enable_funded_trading else "cycles.jsonl"),
            journal_path=settings.execution_journal_path,
        ),
        journal_path=journal,
        control=control,
        control_port=args.port,
    )
    uvicorn.run(create_app(ctx), host="127.0.0.1", port=args.port, log_level="info")


if __name__ == "__main__":
    main()
