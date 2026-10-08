"""Dry-run demo bot on REAL market data from the local MT5 DEMO terminal (read-only).

What it does on every closed M15 bar: refresh the raw store from the terminal (market data only),
build the signal from closed bars, pass it through the signal bridge (risk engine, safety, kill
switch, idempotency) and append one line to the cycle journal. It NEVER submits an order: no
execution adapter exists yet, and this script refuses to start unless dry-run is on.

Usage (Windows, MT5 extra installed, terminal logged in to a DEMO account):
    uv run --extra mt5 python scripts/demo_trader.py --once
    uv run --extra mt5 python scripts/demo_trader.py            # loop, one cycle per M15 close

The magic number is read from XAU_EDGE_DEMO_MAGIC (or --magic); without it every signal is refused.
Stop with Ctrl+C. Trip the kill switch with ``scripts/kill_switch.py`` (see the runbook).
"""

from __future__ import annotations

import argparse
import contextlib
import sys
import time
from datetime import UTC, datetime, timedelta
from functools import partial
from pathlib import Path

from xau_edge.brokers.mt5_demo.reader import DemoAccountError, DemoReader
from xau_edge.config import Settings
from xau_edge.domain.timeframe import Timeframe
from xau_edge.execution.bridge import SignalBridge
from xau_edge.execution.journal import ExecutionJournal
from xau_edge.execution.reconcile import Reconciler
from xau_edge.execution.runner import (
    CycleJournal,
    DryRunCycle,
    LockHeldError,
    acquire_lock,
    next_close,
    write_heartbeat,
)
from xau_edge.execution.safety import ExecutionSafety, assert_live_trading_disabled
from xau_edge.execution.state import ExecutionState, PersistentKillSwitch
from xau_edge.experiments.registry import ExperimentRegistry
from xau_edge.market_data.catalog import DatasetCatalog
from xau_edge.market_data.mt5.source import (
    Mt5BarSource,
    Mt5Settings,
    load_mt5_module,
)
from xau_edge.market_data.profiles import BrokerProfile
from xau_edge.market_data.refresh import refresh_market_data
from xau_edge.market_data.store import RawStore
from xau_edge.market_data.validators import validate_bars
from xau_edge.observability import configure_logging
from xau_edge.risk.engine import AccountState, RiskEngine, RiskLimits
from xau_edge.risk.prop_rules import load_prop_profile
from xau_edge.signals.engine import MarketFrames, generate_signal
from xau_edge.signals.schema import Signal

DEFAULT_TERMINAL = r"C:\Program Files\FTMO Global Markets MT5 Terminal\terminal64.exe"
SETTLE_SECONDS = 20
"""Wait this long after an M15 close so the terminal has the finished bar."""


def generate_signal_for(frames: MarketFrames, registry: ExperimentRegistry, at: datetime) -> Signal:
    """Signal at ``at`` from a fixed set of frames (bound per cycle)."""
    return generate_signal(frames, at, registry)


def main() -> int:  # noqa: PLR0911 - one exit code per refusal
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("--once", action="store_true", help="run a single cycle and exit")
    parser.add_argument("--terminal-path", default=DEFAULT_TERMINAL)
    parser.add_argument("--symbol", default="XAUUSD")
    parser.add_argument("--profile", default="configs/brokers/ftmo_demo.yaml")
    parser.add_argument("--prop", default="configs/prop/ftmo_2step.yaml")
    parser.add_argument("--data-dir", default="data")
    parser.add_argument("--magic", type=int, default=None)
    parser.add_argument("--force", action="store_true", help="re-decide an already journalled bar")
    args = parser.parse_args()
    configure_logging("WARNING")
    assert_live_trading_disabled()

    settings = Settings()
    if not settings.demo_dry_run:
        print("REFUSING: XAU_EDGE_DEMO_DRY_RUN=false, but order submission is not implemented.")
        return 2
    magic = args.magic if args.magic is not None else settings.demo_magic

    data_dir = Path(args.data_dir)
    exec_dir = data_dir / "execution"
    try:
        acquire_lock(exec_dir / "demo_trader.lock")
    except LockHeldError as exc:
        print(exc, file=sys.stderr)
        return 4
    profile = BrokerProfile.from_yaml(args.profile)
    state = ExecutionState(settings.demo_state_path)
    risk = RiskEngine(RiskLimits(), load_prop_profile(args.prop), PersistentKillSwitch(state))
    safety = ExecutionSafety(
        allowed_symbols=tuple(s.strip() for s in settings.demo_allowed_symbols.split(",")),
        max_lots=settings.demo_max_lots,
        max_orders_per_day=settings.demo_max_orders_per_day,
        dry_run=True,
    )
    bridge = SignalBridge(state, risk, safety, magic=magic, dry_run=True)
    registry = ExperimentRegistry("experiments/runs")
    journal = CycleJournal(exec_dir / "cycles.jsonl")
    audit = ExecutionJournal(settings.demo_journal_path)
    allowed_accounts = tuple(
        a.strip() for a in settings.demo_allowed_accounts.split(",") if a.strip()
    )
    reconciler = Reconciler(
        state, magic=magic, symbols=(args.symbol,), allowed_accounts=allowed_accounts
    )  # observe only: the dry-run never trips the kill switch
    store = RawStore(data_dir / "raw")

    mt5 = load_mt5_module()
    reader = DemoReader(mt5, profile.clock, args.symbol)
    if not mt5.initialize(path=args.terminal_path, timeout=90000):
        print(f"MT5 initialize failed: {mt5.last_error()}")
        (exec_dir / "demo_trader.lock").unlink(missing_ok=True)
        return 2
    try:
        try:
            reader.account()
        except DemoAccountError as exc:
            print(f"REFUSING: {exc}")
            return 3
        mt5.symbol_select(args.symbol, True)
        source = Mt5BarSource(mt5, Mt5Settings(broker_timezone=profile.clock.token))
        print(
            f"dry-run demo bot started (read-only, never sends orders); magic={'set' if magic is not None else 'MISSING'}"
        )
        while True:
            now = datetime.now(UTC)
            refresh_market_data(source, store, args.symbol, now, source_name=f"mt5-{profile.name}")
            catalog = DatasetCatalog(data_dir / "raw")
            loaded = {tf: catalog.load(args.symbol, tf).frame for tf in Timeframe}
            invalid = [
                tf.value
                for tf, frame in loaded.items()
                if not validate_bars(
                    frame, tf, symbol=args.symbol, config=profile.validation
                ).passed
            ]
            frames = MarketFrames(
                loaded[Timeframe.M5],
                loaded[Timeframe.M15],
                loaded[Timeframe.H1],
                loaded[Timeframe.H4],
            )
            try:
                snapshot = reader.snapshot(now)
            except DemoAccountError as exc:
                print(f"{now:%H:%M:%S} account/positions unavailable ({exc}); cycle skipped")
                audit.record("snapshot.failed", error=str(exc))
                write_heartbeat(exec_dir / "heartbeat.json", now, "ACCOUNT_UNAVAILABLE")
                if args.once:
                    return 5
                time.sleep(30)
                continue
            reconcile = reconciler.check(snapshot)
            audit.record("reconcile.result", clean=reconcile.clean, codes=list(reconcile.codes))
            balance = snapshot.account.balance
            account = AccountState(
                timestamp=now,
                initial_capital=balance,
                balance=balance,
                equity=snapshot.account.equity,
                day_start_balance=balance,
                highest_eod_balance=balance,
                open_positions=len(snapshot.positions),
                open_lots=sum(p.lots for p in snapshot.positions),
                risk_taken_today=0.0,
                consecutive_losses=0,
            )
            cycle = DryRunCycle(bridge, partial(generate_signal_for, frames, registry), journal)
            if invalid:
                print(f"{now:%H:%M:%S} data validation failed for {invalid}; cycle skipped")
                write_heartbeat(exec_dir / "heartbeat.json", now, "DATA_INVALID")
            else:
                report = cycle.run(frames, now, account, force=args.force, reconcile=reconcile)
                print(
                    f"{now:%H:%M:%S} bar {report.decision_time} {report.direction} "
                    f"accepted={report.accepted} reasons={list(report.reasons)}"
                )
                write_heartbeat(exec_dir / "heartbeat.json", now, "OK")
            if args.once:
                return 0
            wake = next_close(datetime.now(UTC)) + timedelta(seconds=SETTLE_SECONDS)
            time.sleep(max(1.0, (wake - datetime.now(UTC)).total_seconds()))
    except KeyboardInterrupt:
        print("stopped by operator")
        return 0
    finally:
        mt5.shutdown()
        with contextlib.suppress(OSError):
            (exec_dir / "demo_trader.lock").unlink(missing_ok=True)


if __name__ == "__main__":
    raise SystemExit(main())
