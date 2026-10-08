"""Pipeline smoke test: send ONE minimum-lot, labelled order to the DEMO account and close it at once.

This tests the order plumbing (gates, order_check, order_send, position lookup, reconciliation,
close). It is NOT evidence about any strategy and never goes through a signal. It refuses unless
every one of these is set explicitly:

    XAU_EDGE_ENABLE_DEMO_TRADING=true  XAU_EDGE_DEMO_SMOKE=true  XAU_EDGE_DEMO_DRY_RUN=false
    XAU_EDGE_DEMO_ALLOWED_ACCOUNTS=<your demo login>  XAU_EDGE_DEMO_MAGIC=<any integer>
    --yes-send-one-demo-order

All the executor's gates still apply (DEMO account, whitelist, kill switch, clean reconciliation,
exactly-once). Usage (Windows, MT5 extra installed):
    uv run --extra mt5 python scripts/smoke_demo_order.py --yes-send-one-demo-order
"""

from __future__ import annotations

import argparse
import time
from datetime import UTC, datetime
from pathlib import Path

from xau_edge.brokers.mt5_demo.connect import TradeConnectError, connect_for_trading
from xau_edge.brokers.mt5_demo.executor import (
    ExecutorConfig,
    Mt5DemoExecutor,
    build_smoke_intent,
)
from xau_edge.brokers.mt5_demo.reader import DemoReader
from xau_edge.config import Settings
from xau_edge.execution.journal import ExecutionJournal
from xau_edge.execution.reconcile import Reconciler
from xau_edge.execution.runner import LockHeldError, acquire_lock
from xau_edge.execution.safety import assert_live_trading_disabled
from xau_edge.execution.state import ExecutionState
from xau_edge.market_data.mt5.source import load_mt5_module
from xau_edge.market_data.profiles import BrokerProfile
from xau_edge.observability import configure_logging

DEFAULT_TERMINAL = r"C:\Program Files\FTMO Global Markets MT5 Terminal\terminal64.exe"


def main() -> int:  # noqa: PLR0911 - one exit code per refusal
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--yes-send-one-demo-order", action="store_true")
    parser.add_argument("--terminal-path", default=DEFAULT_TERMINAL)
    parser.add_argument("--profile", default="configs/brokers/ftmo_demo.yaml")
    parser.add_argument("--symbol", default="XAUUSD")
    parser.add_argument("--hold-seconds", type=float, default=3.0)
    args = parser.parse_args()
    configure_logging("WARNING")
    assert_live_trading_disabled()
    if not args.yes_send_one_demo_order:
        print("REFUSING: pass --yes-send-one-demo-order to confirm one DEMO order.")
        return 2
    settings = Settings()
    if not (settings.enable_demo_trading and settings.demo_smoke and not settings.demo_dry_run):
        print("REFUSING: demo trading, smoke mode and dry-run=false must be set explicitly.")
        return 2
    accounts = tuple(a.strip() for a in settings.demo_allowed_accounts.split(",") if a.strip())
    symbols = tuple(s.strip() for s in settings.demo_allowed_symbols.split(",") if s.strip())
    if args.symbol not in symbols:
        print(f"REFUSING: {args.symbol} is not in XAU_EDGE_DEMO_ALLOWED_SYMBOLS.")
        return 2
    try:
        acquire_lock(Path("data/execution/demo_trader.lock"))  # never run beside the bot
    except LockHeldError as exc:
        print(exc)
        return 4
    profile = BrokerProfile.from_yaml(args.profile)
    state = ExecutionState(settings.demo_state_path)
    journal = ExecutionJournal(settings.demo_journal_path)
    mt5 = load_mt5_module()
    reader = DemoReader(mt5, profile.clock, args.symbol)
    try:
        connect_for_trading(mt5, reader, args.terminal_path)
    except TradeConnectError as exc:
        print(f"REFUSING: {exc}")
        Path("data/execution/demo_trader.lock").unlink(missing_ok=True)
        return 3
    try:
        mt5.symbol_select(args.symbol, True)
        reconciler = Reconciler(
            state,
            magic=settings.demo_magic,
            symbols=(args.symbol,),
            allowed_accounts=accounts,
            trip_on_mismatch=True,
        )
        executor = Mt5DemoExecutor(
            mt5,
            reader,
            state,
            journal,
            reconciler,
            ExecutorConfig(
                enabled=True,
                dry_run=False,
                allowed_accounts=accounts,
                symbols=symbols,
                magic=settings.demo_magic,
                max_lots=settings.demo_max_lots,
                deviation_points=settings.demo_deviation_points,
                smoke=True,
            ),
        )
        tick = mt5.symbol_info_tick(args.symbol)
        if tick is None or settings.demo_magic is None:
            print("REFUSING: no price or no magic number.")
            return 2
        now = datetime.now(UTC)
        intent = build_smoke_intent(
            float(tick.ask), now, magic=settings.demo_magic, symbol=args.symbol
        )
        result = executor.submit_smoke(intent, now)
        print(f"submit: {result.status} reasons={list(result.reasons)} retcode={result.retcode}")
        if result.status != "FILLED" or result.ticket is None:
            return 0 if result.status in ("REFUSED", "REJECTED") else 1
        time.sleep(args.hold_seconds)
        closed = executor.close_position(result.ticket, "SMOKE_DONE")
        print(f"close: {closed.status} reasons={list(closed.reasons)} retcode={closed.retcode}")
        clean = reconciler.check(reader.snapshot(datetime.now(UTC)))
        print(f"reconciliation after close: {'clean' if clean.clean else list(clean.codes)}")
        return 0 if closed.status == "FILLED" and clean.clean else 1
    finally:
        mt5.shutdown()
        Path("data/execution/demo_trader.lock").unlink(missing_ok=True)


if __name__ == "__main__":
    raise SystemExit(main())
