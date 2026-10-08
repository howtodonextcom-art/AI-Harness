"""The XAUUSD bot on the local MT5 terminal: DRY-RUN, DEMO or FUNDED (ADR-0019, ADR-0020).

The mode comes from ``.env``, never from this command line:

* DRY-RUN (default): reads market data and the account, runs every gate, journals the decision and
  NEVER sends an order (no executor exists in this mode).
* DEMO (``XAU_EDGE_ENABLE_DEMO_TRADING=true`` + ``XAU_EDGE_DEMO_DRY_RUN=false``): CAN SEND ORDERS
  to a whitelisted DEMO account, behind the evidence gate, risk engine, execution safety, kill
  switch, idempotency and reconciliation.
* FUNDED (``XAU_EDGE_ENABLE_FUNDED_TRADING=true``): CAN SEND ORDERS to the whitelisted FTMO funded
  account, only when every ``must_verify`` rule in ``configs/prop/ftmo_funded.yaml`` is verified,
  and only as the rollout tier allows (tier 0 = shadow: ``order_check`` only, nothing is sent).

The web control plane (ADR-0023) may choose between DRY-RUN and DEMO through
``data/execution/runtime_mode.json``; ``.env`` stays the upper bound (no demo trading in ``.env`` =
DRY-RUN whatever the file says), FUNDED is never read from that file, and a file holding anything
other than DRY_RUN or DEMO refuses the start. A soft stop requested from the web ends the loop
between cycles.

DEMO and FUNDED refuse to start without ``--confirm-mode DEMO`` / ``--confirm-mode FUNDED``. The
start-up banner prints the mode, server, trade_mode, rules profile and the account's last three
digits. Trade-server requests (order_check/order_send) have a hard budget of 900 per Prague day;
every other terminal call is counted for monitoring but never stopped.

Usage (Windows, MT5 extra installed, terminal logged in):
    uv run --extra mt5 python scripts/demo_trader.py --once                       # dry-run
    uv run --extra mt5 python scripts/demo_trader.py --confirm-mode DEMO          # demo loop
    uv run --extra mt5 python scripts/demo_trader.py --confirm-mode FUNDED        # funded loop

Exit codes:
    0  stopped normally (--once / --max-cycles reached, or Ctrl+C)
    2  the terminal could not be initialised
    3  start refused: account, server, whitelist, rules file, rollout or confirmation
    4  another instance holds the lock file
    5  --once and the cycle hit a transient terminal error
    6  fatal error (state, journal, account type); the supervisor restarts the process
    7  repeated unclassified errors

Trip the kill switch with ``scripts/kill_switch.py``; see the rollout with ``scripts/rollout.py``.
"""

from __future__ import annotations

import argparse
import contextlib
import sys
from collections.abc import Callable
from datetime import UTC, datetime
from functools import partial
from pathlib import Path
from typing import Any

from xau_edge.brokers.mt5_demo.connect import TradeConnectError, connect_for_trading
from xau_edge.brokers.mt5_demo.executor import TRADE_SERVER_REQUESTS, Mt5DemoExecutor
from xau_edge.brokers.mt5_demo.reader import DemoAccountError, DemoReader
from xau_edge.config import Settings
from xau_edge.control.paths import RUNTIME_MODE_FILE, STOP_FILE
from xau_edge.control.runtime_mode import (
    RuntimeModeError,
    apply_runtime_mode,
    describe_settings_error,
    read_runtime_mode,
)
from xau_edge.control.sentinel import StopSentinel
from xau_edge.domain.timeframe import Timeframe
from xau_edge.execution.app import AlertFn, BotApp
from xau_edge.execution.bridge import SignalBridge
from xau_edge.execution.guards import DAILY_REQUEST_BUDGET, CountingMt5, EntryGuard
from xau_edge.execution.journal import ExecutionJournal
from xau_edge.execution.reconcile import Reconciler
from xau_edge.execution.runner import CycleJournal, DryRunCycle, LockHeldError, acquire_lock
from xau_edge.execution.safety import assert_live_trading_disabled
from xau_edge.execution.state import ExecutionState, PersistentKillSwitch
from xau_edge.experiments.registry import ExperimentRegistry
from xau_edge.funded.identity import AccountIdentity, ModeError, RunMode, banner, requested_mode
from xau_edge.funded.plan import RunPlan, build_run_plan
from xau_edge.funded.rollout import RolloutController, load_rollout
from xau_edge.funded.rules import FundedRules, FundedRulesNotVerifiedError, load_funded_rules
from xau_edge.funded.wiring import (
    PropFacts,
    alert_fn,
    execution_safety,
    executor_config,
    make_submit,
    risk_limits,
    rollout_announcement,
    strategy_validated,
)
from xau_edge.market_data.catalog import DatasetCatalog
from xau_edge.market_data.mt5.source import Mt5BarSource, Mt5Settings, load_mt5_module
from xau_edge.market_data.profiles import BrokerProfile
from xau_edge.market_data.refresh import refresh_market_data
from xau_edge.market_data.store import RawStore
from xau_edge.market_data.validators import validate_bars
from xau_edge.news.calendar import StaticCalendar, load_calendar_file
from xau_edge.ops.clock_check import check_clock
from xau_edge.ops.logging_setup import setup_service_logging
from xau_edge.ops.notifier import build_dispatcher
from xau_edge.ops.settings import OpsSettings
from xau_edge.risk.engine import RiskEngine
from xau_edge.risk.prop_rules import PropProfile, load_prop_profile
from xau_edge.signals.engine import MarketFrames, generate_signal
from xau_edge.signals.schema import Signal
from xau_edge.signals.strategy_registry import StrategySpec, default_strategy

DEFAULT_TERMINAL = r"C:\Program Files\FTMO Global Markets MT5 Terminal\terminal64.exe"
EXIT_OK = 0
EXIT_INIT_FAILED = 2
EXIT_REFUSED = 3
EXIT_LOCKED = 4


def build_parser() -> argparse.ArgumentParser:
    """The command line (the mode itself is configuration, not a flag)."""
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("--once", action="store_true", help="run a single cycle and exit")
    parser.add_argument("--max-cycles", type=int, default=0, help="stop after N cycles (0 = never)")
    parser.add_argument(
        "--confirm-mode",
        default=None,
        choices=[RunMode.DEMO.value, RunMode.FUNDED.value],
        help="required to start an order-sending mode; must equal the configured mode",
    )
    parser.add_argument("--terminal-path", default=DEFAULT_TERMINAL)
    parser.add_argument("--symbol", default="XAUUSD")
    parser.add_argument("--profile", default="configs/brokers/ftmo_demo.yaml")
    parser.add_argument("--prop", default="configs/prop/ftmo_2step.yaml", help="dry-run/demo only")
    parser.add_argument("--data-dir", default=None, help="default: XAU_EDGE_DATA_DIR")
    parser.add_argument("--force", action="store_true", help="re-decide an already journalled bar")
    return parser


def generate_signal_for(
    frames: MarketFrames,
    registry: ExperimentRegistry,
    calendar: StaticCalendar | None,
    strategy: StrategySpec,
    at: datetime,
) -> Signal:
    """Signal at ``at`` from a fixed set of frames (bound per cycle)."""
    return generate_signal(frames, at, registry, calendar=calendar, strategy=strategy)


def _funded_inputs(
    settings: Settings, state: ExecutionState, *, validated: bool
) -> tuple[FundedRules | None, RolloutController | None]:
    """The rules file and rollout controller; a missing or broken file leaves ``None`` (refused)."""
    try:
        rules: FundedRules | None = load_funded_rules(settings.funded_profile_path)
    except (OSError, ValueError) as exc:
        print(f"funded rules file unreadable: {exc}", file=sys.stderr)
        rules = None
    try:
        config = load_rollout(settings.funded_rollout_path)
    except (OSError, ValueError) as exc:
        print(f"rollout file unreadable: {exc}", file=sys.stderr)
        return rules, None
    return rules, RolloutController(state, config, validated=validated)


def main() -> int:
    args = build_parser().parse_args()
    assert_live_trading_disabled()
    settings = Settings()
    ops = OpsSettings()
    setup_service_logging(ops.log_file, file_level="INFO")
    data_dir = Path(args.data_dir) if args.data_dir else settings.data_dir
    exec_dir = data_dir / "execution"
    lock = exec_dir / "demo_trader.lock"
    started_at = datetime.now(UTC)
    try:
        acquire_lock(lock)
    except LockHeldError as exc:
        print(exc, file=sys.stderr)
        return EXIT_LOCKED
    try:
        try:
            settings, note = apply_runtime_mode(
                settings, read_runtime_mode(exec_dir / RUNTIME_MODE_FILE)
            )
        except RuntimeModeError as exc:
            print(f"REFUSING: {exc}")
            return EXIT_REFUSED
        except ValueError as exc:
            print(f"REFUSING: DEMO from the web needs: {describe_settings_error(exc)}")
            return EXIT_REFUSED
        if note:
            print(f"NOTE: {note}")
        stop = StopSentinel(exec_dir / STOP_FILE, started_at)
        return _run(args, settings, ops, data_dir, exec_dir, stop=stop)
    except KeyboardInterrupt:
        print("stopped by operator")
        return EXIT_OK
    finally:
        with contextlib.suppress(OSError):
            lock.unlink(missing_ok=True)


def _run(
    args: argparse.Namespace,
    settings: Settings,
    ops: OpsSettings,
    data_dir: Path,
    exec_dir: Path,
    *,
    stop: Callable[[], bool],
) -> int:
    requested = requested_mode(settings)
    funded = requested is RunMode.FUNDED
    state = ExecutionState(settings.funded_state_path if funded else settings.demo_state_path)
    counter = CountingMt5(
        load_mt5_module(), state, budgeted=TRADE_SERVER_REQUESTS, budget=DAILY_REQUEST_BUDGET
    )
    mt5: Any = counter
    profile = BrokerProfile.from_yaml(args.profile)
    reader = DemoReader(mt5, profile.clock, args.symbol, require_demo=not funded)
    alert = alert_fn(build_dispatcher(ops, fallback_path=exec_dir / "alerts.jsonl"))
    sends = requested is not RunMode.DRY_RUN

    def connect() -> None:
        if sends:
            connect_for_trading(mt5, reader, args.terminal_path)
        elif not mt5.initialize(path=args.terminal_path, timeout=90000):
            msg = f"MT5 initialize failed: {mt5.last_error()}"
            raise ConnectionError(msg)
        mt5.symbol_select(args.symbol, True)

    try:
        connect()
    except TradeConnectError as exc:
        print(f"REFUSING: {exc}")
        return EXIT_REFUSED
    except ConnectionError as exc:
        print(exc)
        return EXIT_INIT_FAILED
    try:
        try:
            account = reader.account()
        except DemoAccountError as exc:
            print(f"REFUSING: {exc}")
            return EXIT_REFUSED
        identity = AccountIdentity(account.account_id, account.server, account.is_demo)
        registry = ExperimentRegistry("experiments/runs")
        spec = default_strategy()
        validated = strategy_validated(registry, spec)
        rules, rollout = (
            _funded_inputs(settings, state, validated=validated) if funded else (None, None)
        )
        try:
            plan = build_run_plan(
                settings,
                identity,
                rules=rules,
                tier=rollout.constraints() if rollout else None,
                validated=validated,
                confirm=args.confirm_mode,
                demo_prop_source=args.prop,
            )
        except (ModeError, FundedRulesNotVerifiedError) as exc:
            print(f"REFUSING to start: {exc}")
            alert("BOT_STOPPED", "critical", f"start refused: {exc}")
            return EXIT_REFUSED
        if plan.require_demo != reader.require_demo or plan.state_path != state.path:
            print("REFUSING: the plan does not match the terminal reader or the state file")
            return EXIT_REFUSED
        prop: PropProfile = (
            rules.to_prop_profile()
            if plan.mode is RunMode.FUNDED and rules is not None
            else load_prop_profile(args.prop)
        )
        print(banner(plan.mode, identity, prop.name))
        print(_summary(plan))
        app = _build_app(
            args,
            settings=settings,
            ops=ops,
            data_dir=data_dir,
            exec_dir=exec_dir,
            plan=plan,
            prop=prop,
            state=state,
            counter=counter,
            reader=reader,
            spec=spec,
            registry=registry,
            rollout=rollout,
            alert=alert,
            connect=connect,
            login=account.account_id,
            stop=stop,
        )
        return app.run(once=args.once, max_cycles=args.max_cycles, force=args.force)
    finally:
        mt5.shutdown()


def _summary(plan: RunPlan) -> str:
    sending = "SENDS ORDERS" if plan.send_orders else "never sends"
    shadow = " (shadow: order_check only)" if plan.shadow else ""
    tier = (
        f" tier={plan.rollout_tier}:{plan.rollout_tier_name}"
        if plan.rollout_tier is not None
        else ""
    )
    return (
        f"{sending}{shadow}; evidence={plan.evidence_label}"
        f"{' strategy=' + plan.strategy_id if plan.strategy_id else ''}{tier} "
        f"risk={plan.risk_pct}%/trade lot_cap={plan.lot_cap or '-'} max_lots={plan.max_lots} "
        f"magic={'set' if plan.magic is not None else 'MISSING'} "
        f"request_budget={DAILY_REQUEST_BUDGET}/day"
    )


def _build_app(
    args: argparse.Namespace,
    *,
    settings: Settings,
    ops: OpsSettings,
    data_dir: Path,
    exec_dir: Path,
    plan: RunPlan,
    prop: PropProfile,
    state: ExecutionState,
    counter: CountingMt5,
    reader: DemoReader,
    spec: StrategySpec,
    registry: ExperimentRegistry,
    rollout: RolloutController | None,
    alert: AlertFn,
    connect: Callable[[], None],
    login: str,
    stop: Callable[[], bool],
) -> BotApp:
    mt5: Any = counter
    profile = BrokerProfile.from_yaml(args.profile)
    symbols = tuple(s.strip() for s in settings.demo_allowed_symbols.split(",") if s.strip())
    risk = RiskEngine(risk_limits(plan), prop, PersistentKillSwitch(state))
    safety = execution_safety(
        plan, account=login, symbols=symbols, max_orders_per_day=settings.demo_max_orders_per_day
    )
    bridge = SignalBridge(
        state,
        risk,
        safety,
        magic=plan.magic,
        dry_run=plan.bridge_dry_run,
        entry_guard=EntryGuard(profile.validation.calendar),
        override=plan.override,
        lot_cap=plan.lot_cap,
    )
    audit = ExecutionJournal(plan.journal_path)
    reconciler = Reconciler(
        state,
        magic=plan.magic,
        symbols=(args.symbol,),
        allowed_accounts=plan.allowed_accounts,
        trip_on_mismatch=plan.uses_executor,  # dry-run only observes
        require_demo=plan.require_demo,
    )
    cfg = executor_config(plan, symbols=symbols, deviation_points=settings.demo_deviation_points)
    executor = (
        Mt5DemoExecutor(mt5, reader, state, audit, reconciler, cfg) if cfg is not None else None
    )
    submit = make_submit(executor, rollout)
    cycle_file = "funded_cycles.jsonl" if plan.mode is RunMode.FUNDED else "cycles.jsonl"
    cycles = CycleJournal(exec_dir / cycle_file)
    store = RawStore(data_dir / "raw")
    source = Mt5BarSource(
        mt5, Mt5Settings(broker_timezone=profile.clock.token), require_demo=plan.require_demo
    )
    calendar = (
        load_calendar_file(settings.news_calendar_path) if settings.news_calendar_path else None
    )
    ntp_servers = tuple(s.strip() for s in ops.ntp_servers.split(",") if s.strip())

    def refresh(now: datetime) -> None:
        refresh_market_data(source, store, args.symbol, now, source_name=f"mt5-{profile.name}")

    def load_frames() -> tuple[MarketFrames, list[str]]:
        catalog = DatasetCatalog(data_dir / "raw")
        loaded = {tf: catalog.load(args.symbol, tf).frame for tf in Timeframe}
        invalid = [
            tf.value
            for tf, frame in loaded.items()
            if not validate_bars(frame, tf, symbol=args.symbol, config=profile.validation).passed
        ]
        frames = MarketFrames(
            loaded[Timeframe.M5], loaded[Timeframe.M15], loaded[Timeframe.H1], loaded[Timeframe.H4]
        )
        return frames, invalid

    def make_cycle(frames: MarketFrames) -> DryRunCycle:
        return DryRunCycle(
            bridge,
            partial(generate_signal_for, frames, registry, calendar, spec),
            cycles,
            submit=submit,
            strategy_id=spec.strategy_id,
        )

    def reconnect() -> None:
        mt5.shutdown()
        connect()

    announcement = rollout_announcement(plan)
    if announcement is not None:
        alert("ROLLOUT_TIER", "info", announcement)
    return BotApp(
        mode=plan.status_mode,
        symbol=args.symbol,
        state=state,
        reader=reader,
        executor=executor,
        reconciler=reconciler,
        risk=risk,
        prop=prop,
        audit=audit,
        refresh=refresh,
        load_frames=load_frames,
        make_cycle=make_cycle,
        exec_dir=exec_dir,
        initial_capital=plan.initial_capital,
        alert=alert,
        ntp_check=lambda: check_clock(ntp_servers),
        reconnect=reconnect,
        max_clock_offset_seconds=ops.ntp_max_offset_seconds,
        prop_facts=PropFacts(
            plan, state, prop, requests_today=counter.used_today, request_budget=counter.budget
        ),
        stop_requested=stop,
    )


if __name__ == "__main__":
    raise SystemExit(main())
