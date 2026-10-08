"""Fakes for the control plane: a bot process, a terminal probe and a service on temporary files.

Nothing here touches a real MT5 terminal, a real NSSM service or the project's real ``.env``: the
settings come from a ``.env`` written into ``tmp_path``.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import timedelta
from pathlib import Path
from typing import Any

from tests.unit.brokers.test_executor import LOGIN, MAGIC, FakeTerminal, T
from xau_edge.brokers.mt5_demo.connect import Mt5TradeSettings
from xau_edge.brokers.mt5_demo.reader import DemoReader
from xau_edge.config import Settings
from xau_edge.control.jobs import JobManager, RateLimiter, RateRule
from xau_edge.control.paths import ControlPaths
from xau_edge.control.preflight import RawTerminal
from xau_edge.control.process import (
    BotState,
    ProcessControlError,
    ProcessInfo,
    StartOutcome,
    StopOutcome,
)
from xau_edge.control.runtime_mode import RuntimeMode
from xau_edge.control.service import ControlConfig, ControlDeps, ControlService
from xau_edge.execution.status import BotStatus, write_status

REPO = Path(__file__).parents[3]
PROFILE = REPO / "configs" / "brokers" / "ftmo_demo.yaml"
FAKE_TRADE_PASSWORD = "pw-NOT-real-7f3a"
TOKEN = "t" * 43


def write_env(tmp_path: Path, **over: str) -> Path:
    """A ``.env`` in ``tmp_path`` (demo enabled, smoke allowed, fake credentials)."""
    values = {
        "XAU_EDGE_ENABLE_DEMO_TRADING": "true",
        "XAU_EDGE_DEMO_ALLOWED_ACCOUNTS": LOGIN,
        "XAU_EDGE_DEMO_MAGIC": str(MAGIC),
        "XAU_EDGE_DEMO_INITIAL_CAPITAL": "100000",
        "XAU_EDGE_DEMO_SMOKE": "true",
        "XAU_EDGE_DEMO_STATE_PATH": str(tmp_path / "data" / "execution" / "state.sqlite"),
        "XAU_EDGE_DEMO_JOURNAL_PATH": str(tmp_path / "data" / "execution" / "journal.jsonl"),
        "MT5_LOGIN": LOGIN,
        "MT5_SERVER": "FTMO-Demo",
        "MT5_TRADE_PASSWORD": FAKE_TRADE_PASSWORD,
    }
    values.update(over)
    path = tmp_path / ".env"
    path.write_text("".join(f"{k}={v}\n" for k, v in values.items()), encoding="utf-8")
    return path


def demo_terminal(login: str = LOGIN, **over: Any) -> RawTerminal:
    """What a logged-in demo terminal answers to the read-only probe."""
    base: dict[str, Any] = {
        "connected": True,
        "login": login,
        "server": "FTMO-Demo",
        "trade_mode_demo": True,
        "terminal_trade_allowed": True,
        "account_trade_allowed": True,
    }
    base.update(over)
    return RawTerminal(**base)


class FakeProcess:
    """A bot that starts and stops on command and writes ``status.json`` like the real one."""

    def __init__(self, paths: ControlPaths) -> None:
        self.paths = paths
        self.state = BotState.STOPPED
        self.calls: list[str] = []
        self.reported_mode: str | None = None
        self.fail_start: str | None = None

    def info(self) -> ProcessInfo:
        pid = 4242 if self.state is BotState.RUNNING else None
        return ProcessInfo(self.state, "subprocess", pid, "fake")

    def start(self, mode: RuntimeMode) -> StartOutcome:
        self.calls.append(f"start:{mode.value}")
        if self.fail_start:
            raise ProcessControlError(self.fail_start, "fake start failure")
        if self.state is BotState.RUNNING:
            raise ProcessControlError("BOT_ALREADY_RUNNING", "running")
        self.state = BotState.RUNNING
        reported = self.reported_mode or ("demo" if mode is RuntimeMode.DEMO else "dry-run")
        self.paths.exec_dir.mkdir(parents=True, exist_ok=True)
        write_status(
            self.paths.status,
            BotStatus(
                updated_at=T + timedelta(seconds=1),
                mode=reported,
                symbol="XAUUSD",
                connected=True,
                account_demo=True,
                balance=None,
                equity=None,
                positions=[],
                reconcile_clean=True,
                reconcile_codes=[],
                last_cycle=None,
                news_status="unknown",
            ),
        )
        return StartOutcome(self.info(), True)

    def stop(self) -> StopOutcome:
        self.calls.append("stop")
        was = self.state is BotState.RUNNING
        self.state = BotState.STOPPED
        return StopOutcome(was, True, 0.0, {"decision_time": "2026-03-04T13:45:00+00:00"}, "mềm")

    def nssm_installed(self) -> bool:
        return False

    def nssm_confirm_mode(self) -> str | None:
        return None


class TradingTerminal(FakeTerminal):
    """The executor tests' fake terminal plus the session calls the control plane makes."""

    def __init__(self) -> None:
        super().__init__()
        self.kill_switch_at_send: list[bool] = []
        self.state_path: Path | None = None

    def initialize(self, **kwargs: Any) -> bool:
        return True

    def shutdown(self) -> None:
        return None

    def symbol_select(self, symbol: str, enable: bool) -> bool:
        return True

    def order_send(self, request: dict[str, Any]) -> Any:
        if self.state_path is not None:
            from xau_edge.execution.state import ExecutionState  # noqa: PLC0415

            self.kill_switch_at_send.append(ExecutionState(self.state_path).kill_switch_state()[0])
        return super().order_send(request)


class Rig:
    """A ``ControlService`` on temporary files with fakes for every side effect."""

    def __init__(
        self,
        tmp_path: Path,
        *,
        terminal: RawTerminal | None = None,
        env: dict[str, str] | None = None,
        strategy: bool | None = False,
    ) -> None:
        self.tmp = tmp_path
        self.env_file = write_env(tmp_path, **(env or {}))
        self.paths = ControlPaths(tmp_path / "data")
        self.paths.exec_dir.mkdir(parents=True, exist_ok=True)
        self.process = FakeProcess(self.paths)
        self.terminal = terminal or demo_terminal()
        self.term = TradingTerminal()
        self.term.state_path = self.paths.exec_dir / "state.sqlite"
        self.probes = 0
        self.connects = 0
        self.t = 0.0
        env_file = self.env_file

        def probe(load: Callable[[], Any], path: str, timeout: float) -> RawTerminal:
            self.probes += 1
            return self.terminal

        def connect(mt5: Any, reader: DemoReader) -> None:
            self.connects += 1

        def sleep(seconds: float) -> None:
            self.t += seconds

        self.deps = ControlDeps(
            load_settings=lambda: Settings(_env_file=env_file),
            load_credentials=lambda: Mt5TradeSettings(_env_file=env_file),
            load_mt5=lambda: self.term,
            connect_trading=connect,
            strategy_check=lambda: strategy,
            now=lambda: T,
            sleep=sleep,
            monotonic=lambda: self.t,
            probe=probe,
        )
        self.limiter = RateLimiter(
            self.paths.limits,
            {
                "smoke": RateRule(timedelta(minutes=10), 5),
                "flatten": RateRule(timedelta(seconds=30)),
            },
            clock=lambda: T,
        )
        self.jobs = JobManager(clock=lambda: T, executor=lambda fn: fn())
        self.service = ControlService(
            ControlConfig(
                repo_root=tmp_path,
                terminal_path="terminal64.exe",
                data_dir=self.paths.data_dir,
                env_file=self.env_file,
                profile_path=PROFILE,
                smoke_hold_seconds=0.0,
                mode_confirm_timeout=10.0,
            ),
            self.deps,
            process=self.process,
            jobs=self.jobs,
            limiter=self.limiter,
            token=TOKEN,
            token_protected=True,
        )

    def journal(self) -> list[dict[str, Any]]:
        import json  # noqa: PLC0415

        path = self.paths.exec_dir / "journal.jsonl"
        if not path.exists():
            return []
        return [json.loads(line) for line in path.read_text("utf-8").splitlines()]
