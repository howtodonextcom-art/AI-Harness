"""Preflight checks (pure) and the read-only terminal probe (fake MT5, timeout, no package)."""

from __future__ import annotations

import threading
from dataclasses import replace
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from tests.unit.brokers.test_executor import T
from xau_edge.config import Settings
from xau_edge.control.preflight import (
    CredentialFacts,
    PreflightInputs,
    PreflightReport,
    RawTerminal,
    build_report,
    probe_terminal,
)
from xau_edge.control.process import BotState, ProcessInfo
from xau_edge.control.runtime_mode import RuntimeMode, RuntimeModeRecord

CREDS = CredentialFacts(has_login=True, has_server=True, has_trade_password=True)
TERMINAL = RawTerminal(
    connected=True,
    login="555",
    server="FTMO-Demo",
    trade_mode_demo=True,
    terminal_trade_allowed=True,
    account_trade_allowed=True,
)


def write_env(tmp_path: Path, **over: str) -> Path:
    values = {
        "XAU_EDGE_ENABLE_DEMO_TRADING": "true",
        "XAU_EDGE_DEMO_ALLOWED_ACCOUNTS": "555",
        "XAU_EDGE_DEMO_MAGIC": "7",
        "XAU_EDGE_DEMO_INITIAL_CAPITAL": "100000",
        "XAU_EDGE_DEMO_SMOKE": "true",
        **over,
    }
    path = tmp_path / ".env"
    path.write_text("".join(f"{k}={v}\n" for k, v in values.items()), encoding="utf-8")
    return path


def _inputs(tmp_path: Path, **over: Any) -> PreflightInputs:
    settings = Settings(_env_file=write_env(tmp_path))
    base = PreflightInputs(
        now=T,
        env_exists=True,
        settings=settings,
        settings_error=None,
        credentials=CREDS,
        process=ProcessInfo(BotState.STOPPED, "subprocess", None, ""),
        runtime=None,
        runtime_error=None,
        terminal=TERMINAL,
        status=None,
        kill_switch=(False, ""),
        clock_offset_seconds=0.2,
        strategy_validated=False,
        token_protected=True,
    )
    return replace(base, **over)


def _status(report: PreflightReport, check: str) -> str:
    found = report.check(check)
    assert found is not None, check
    return found.status


def test_a_ready_demo_setup_has_no_fail_and_no_demo_blocker(tmp_path: Path) -> None:
    report = build_report(_inputs(tmp_path))
    assert report.has_fail is False
    assert report.demo_blockers == []
    assert report.account_label == "DEMO ***"  # a 3-digit login is masked entirely
    assert report.mode_ceiling is RuntimeMode.DEMO
    assert report.configured_mode is RuntimeMode.DRY_RUN
    assert _status(report, "strategy") == "warn"


def test_a_tripped_kill_switch_fails_and_shows_the_cli_reset(tmp_path: Path) -> None:
    report = build_report(_inputs(tmp_path, kill_switch=(True, "DAILY_FLOOR")))
    check = report.check("kill_switch")
    assert check is not None
    assert check.status == "fail"
    assert "kill_switch.py reset" in check.fix_hint
    assert "KILL_SWITCH_TRIPPED" in {b.code for b in report.demo_blockers}


def test_a_non_demo_terminal_fails(tmp_path: Path) -> None:
    report = build_report(_inputs(tmp_path, terminal=replace(TERMINAL, trade_mode_demo=False)))
    assert _status(report, "mt5.trade_mode") == "fail"
    assert "NOT_DEMO_ACCOUNT" in {b.code for b in report.demo_blockers}


def test_missing_credentials_block_demo_without_naming_values(tmp_path: Path) -> None:
    creds = CredentialFacts(has_login=True, has_server=True, has_trade_password=False)
    report = build_report(_inputs(tmp_path, credentials=creds))
    assert "NO_TRADE_PASSWORD" in {b.code for b in report.demo_blockers}
    assert _status(report, "env.trade_password") == "warn"


def test_a_running_bot_is_read_from_status_and_leaves_demo_unverified(tmp_path: Path) -> None:
    running = ProcessInfo(BotState.RUNNING, "subprocess", 42, "")
    report = build_report(_inputs(tmp_path, process=running, terminal=None))
    assert report.terminal_source == "none"
    assert report.demo_unverified
    assert _status(report, "mt5.account") == "unknown"


def test_a_clock_drift_fails(tmp_path: Path) -> None:
    report = build_report(_inputs(tmp_path, clock_offset_seconds=12.0))
    assert _status(report, "clock.ntp") == "fail"
    assert "PREFLIGHT_FAIL" in {b.code for b in report.demo_blockers}


def test_a_short_news_coverage_warns(tmp_path: Path) -> None:
    settings = Settings(_env_file=write_env(tmp_path, XAU_EDGE_NEWS_CALENDAR_PATH="cal.csv"))
    report = build_report(
        _inputs(tmp_path, settings=settings, news_coverage_end=T + timedelta(days=2))
    )
    assert _status(report, "news.calendar") == "warn"


def test_a_runtime_file_asking_demo_above_the_env_ceiling_warns(tmp_path: Path) -> None:
    env = write_env(tmp_path, XAU_EDGE_ENABLE_DEMO_TRADING="false", XAU_EDGE_DEMO_SMOKE="false")
    settings = Settings(_env_file=env)
    record = RuntimeModeRecord(mode=RuntimeMode.DEMO, set_at=T)
    report = build_report(_inputs(tmp_path, settings=settings, runtime=record))
    assert _status(report, "runtime.mode") == "warn"
    assert report.configured_mode is RuntimeMode.DRY_RUN


def test_an_invalid_env_fails_without_repeating_it(tmp_path: Path) -> None:
    report = build_report(
        _inputs(tmp_path, settings=None, settings_error="demo_magic: Input should be an integer")
    )
    assert _status(report, "env.settings") == "fail"
    assert report.has_fail


# -- probe -------------------------------------------------------------------------------------


class ProbeMt5:
    ACCOUNT_TRADE_MODE_DEMO = 0

    def __init__(self, *, init: bool = True, account: bool = True, block: bool = False) -> None:
        self.init = init
        self.account = account
        self.block = threading.Event() if block else None
        self.calls: list[str] = []

    def initialize(self, **kwargs: Any) -> bool:
        self.calls.append("initialize")
        assert "password" not in kwargs
        if self.block is not None:
            self.block.wait(5)
        return self.init

    def terminal_info(self) -> Any:
        return SimpleNamespace(trade_allowed=True)

    def account_info(self) -> Any:
        if not self.account:
            return None
        return SimpleNamespace(login=12345678, server="FTMO-Demo", trade_mode=0, trade_allowed=True)

    def shutdown(self) -> None:
        self.calls.append("shutdown")

    def order_send(self, request: Any) -> Any:  # pragma: no cover - must never be reached
        raise AssertionError("the probe must never trade")


def test_the_probe_reads_the_account_and_always_shuts_down() -> None:
    mt5 = ProbeMt5()
    raw = probe_terminal(lambda: mt5, "terminal64.exe", timeout_seconds=1)
    assert raw.connected is True
    assert raw.login == "12345678"
    assert raw.trade_mode_demo is True
    assert mt5.calls == ["initialize", "shutdown"]


def test_the_probe_reports_init_failure_and_no_login() -> None:
    assert probe_terminal(lambda: ProbeMt5(init=False), "t", timeout_seconds=1).error == (
        "INITIALIZE_FAILED"
    )
    assert probe_terminal(lambda: ProbeMt5(account=False), "t", timeout_seconds=1).error == (
        "NO_ACCOUNT_LOGGED_IN"
    )


def test_the_probe_reports_a_missing_package() -> None:
    def load() -> Any:
        raise ImportError("MetaTrader5")

    assert probe_terminal(load, "t", timeout_seconds=1).error == "MT5_PACKAGE_MISSING"


def test_the_probe_never_hangs() -> None:
    mt5 = ProbeMt5(block=True)
    raw = probe_terminal(lambda: mt5, "t", timeout_seconds=0.05, margin_seconds=0.0)
    assert mt5.block is not None
    mt5.block.set()
    assert raw.connected is None
    assert raw.error == "TIMEOUT"
