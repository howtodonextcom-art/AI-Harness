"""Preflight: every operating condition of the bot as a list of checks (F1, ADR-0023).

``build_report`` is a pure function of the gathered facts; ``probe_terminal`` is the only part that
touches MT5, read-only (initialize, terminal_info, account_info, shutdown through the query-only
proxy) and bounded by a timeout. Secrets never enter a check: credentials are reported as present
or missing, an account number only as its last three digits, and no file path is ever shown.
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from xau_edge.brokers.mt5_demo.reader import QueryOnlyMt5
from xau_edge.config import Settings
from xau_edge.control.process import BotState, ProcessInfo
from xau_edge.control.runtime_mode import (
    RuntimeMode,
    RuntimeModeRecord,
    effective_mode,
    env_ceiling,
)
from xau_edge.execution.status import BotStatus
from xau_edge.funded.identity import mask_login

CheckStatus = Literal["ok", "warn", "fail", "unknown"]
TerminalSource = Literal["terminal", "status.json", "none"]
SYMBOL = "XAUUSD"
STATUS_STALE_MINUTES = 40
NEWS_MIN_DAYS = 7
RESET_COMMAND = 'uv run python scripts/kill_switch.py reset --confirm "I understand the risk"'


class PreflightCheck(BaseModel):
    """One line of the preflight."""

    model_config = ConfigDict(frozen=True)

    id: str
    label: str
    status: CheckStatus
    detail: str
    fix_hint: str = ""


class Blocker(BaseModel):
    """Why an action is not available now (machine code + Vietnamese message)."""

    model_config = ConfigDict(frozen=True)

    code: str
    message: str


class PreflightReport(BaseModel):
    """The whole preflight answer."""

    model_config = ConfigDict(frozen=True)

    generated_at: datetime
    checks: list[PreflightCheck]
    has_fail: bool
    counts: dict[str, int]
    terminal_source: TerminalSource
    account_label: str | None
    strategy_validated: bool | None
    configured_mode: RuntimeMode
    mode_ceiling: RuntimeMode
    demo_blockers: list[Blocker]
    """Conditions of F3 that are known to be unmet (an unverified terminal is listed separately)."""
    demo_unverified: list[str]
    """F3 conditions that could not be checked now (bot running: terminal not contacted)."""
    smoke_enabled: bool

    def check(self, check_id: str) -> PreflightCheck | None:
        """The check with this id."""
        return next((c for c in self.checks if c.id == check_id), None)

    def failing(self) -> list[str]:
        """Ids of the failed checks."""
        return [c.id for c in self.checks if c.status == "fail"]


@dataclass(frozen=True)
class RawTerminal:
    """What the terminal answered; the login never leaves ``build_report`` unmasked."""

    connected: bool | None
    login: str | None = None
    server: str | None = None
    trade_mode_demo: bool | None = None
    terminal_trade_allowed: bool | None = None
    account_trade_allowed: bool | None = None
    error: str | None = None


@dataclass(frozen=True)
class CredentialFacts:
    """Presence of the MT5 credentials (never their values)."""

    has_login: bool
    has_server: bool
    has_trade_password: bool


@dataclass(frozen=True)
class PreflightInputs:
    """Everything the checks look at, gathered by the control service."""

    now: datetime
    env_exists: bool
    settings: Settings | None
    settings_error: str | None
    credentials: CredentialFacts
    process: ProcessInfo
    runtime: RuntimeModeRecord | None
    runtime_error: str | None
    terminal: RawTerminal | None
    status: BotStatus | None
    kill_switch: tuple[bool | None, str]
    news_coverage_end: datetime | None = None
    news_error: str | None = None
    funded_pending: int | None = None
    clock_offset_seconds: float | None = None
    max_clock_offset_seconds: float = 5.0
    strategy_validated: bool | None = None
    nssm_installed: bool = False
    nssm_confirm_mode: str | None = None
    files_writable: bool = True
    token_protected: bool | None = None
    notes: dict[str, str] = field(default_factory=dict)


def _csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def _yes(flag: bool) -> str:
    return "có" if flag else "không"


class _Builder:
    def __init__(self) -> None:
        self.checks: list[PreflightCheck] = []

    def add(self, cid: str, label: str, status: CheckStatus, detail: str, hint: str = "") -> None:
        self.checks.append(
            PreflightCheck(id=cid, label=label, status=status, detail=detail, fix_hint=hint)
        )


def _env_checks(b: _Builder, i: PreflightInputs) -> None:
    b.add(
        "env.file",
        "File .env",
        "ok" if i.env_exists else "fail",
        "có" if i.env_exists else "không tìm thấy .env ở thư mục dự án",
        "" if i.env_exists else "Sao chép .env.example thành .env rồi điền giá trị.",
    )
    s = i.settings
    if s is None:
        b.add(
            "env.settings",
            "Cấu hình hợp lệ",
            "fail",
            i.settings_error or "không đọc được",
            "Sửa .env theo thông báo; bot sẽ không khởi động.",
        )
        return
    b.add("env.settings", "Cấu hình hợp lệ", "ok", "Settings đọc được")
    b.add("env.live", "Live trading tắt", "ok", "XAU_EDGE_ENABLE_LIVE_TRADING=false (luôn bị khóa)")
    b.add(
        "env.funded",
        "Funded tắt",
        "fail" if s.enable_funded_trading else "ok",
        "FUNDED đang bật trong .env"
        if s.enable_funded_trading
        else "XAU_EDGE_ENABLE_FUNDED_TRADING=false",
        "Web chỉ điều khiển DRY-RUN/DEMO; tắt FUNDED trong .env."
        if s.enable_funded_trading
        else "",
    )
    b.add(
        "env.demo_trading",
        "Demo trading bật",
        "ok" if s.enable_demo_trading else "warn",
        _yes(s.enable_demo_trading),
        ""
        if s.enable_demo_trading
        else "Muốn DEMO: XAU_EDGE_ENABLE_DEMO_TRADING=true (chỉ DRY-RUN tới khi bật).",
    )
    accounts = _csv(s.demo_allowed_accounts)
    b.add(
        "env.accounts",
        "Whitelist tài khoản demo",
        "ok" if accounts else "warn",
        f"có ({len(accounts)} tài khoản)" if accounts else "trống",
        "" if accounts else "Đặt XAU_EDGE_DEMO_ALLOWED_ACCOUNTS=<login demo>.",
    )
    symbols = _csv(s.demo_allowed_symbols)
    b.add(
        "env.symbols",
        "Whitelist symbol có XAUUSD",
        "ok" if SYMBOL in symbols else "warn",
        _yes(SYMBOL in symbols),
        "" if SYMBOL in symbols else "Đặt XAU_EDGE_DEMO_ALLOWED_SYMBOLS=XAUUSD.",
    )
    b.add(
        "env.magic",
        "Magic number",
        "ok" if s.demo_magic is not None else "warn",
        _yes(s.demo_magic is not None),
        "" if s.demo_magic is not None else "Đặt XAU_EDGE_DEMO_MAGIC=<số nguyên>.",
    )
    b.add(
        "env.initial_capital",
        "Vốn ban đầu demo",
        "ok" if s.demo_initial_capital is not None else "warn",
        _yes(s.demo_initial_capital is not None),
        "" if s.demo_initial_capital is not None else "Đặt XAU_EDGE_DEMO_INITIAL_CAPITAL.",
    )
    c = i.credentials
    complete = c.has_login and c.has_server and c.has_trade_password
    b.add(
        "env.trade_password",
        "MT5_TRADE_PASSWORD",
        "ok" if complete else "warn",
        f"trade password: {_yes(c.has_trade_password)}; login: {_yes(c.has_login)}; "
        f"server: {_yes(c.has_server)}",
        "" if complete else "Chủ dự án tự điền MT5_LOGIN, MT5_SERVER, MT5_TRADE_PASSWORD vào .env.",
    )
    b.add(
        "env.smoke",
        "Smoke được phép (.env)",
        "ok" if s.demo_smoke else "warn",
        _yes(s.demo_smoke),
        "" if s.demo_smoke else "Smoke từ web cần XAU_EDGE_DEMO_SMOKE=true trong .env.",
    )


def _runtime_check(b: _Builder, i: PreflightInputs) -> None:
    if i.runtime_error:
        b.add(
            "runtime.mode",
            "Chế độ runtime",
            "fail",
            i.runtime_error,
            "Chọn lại DRY-RUN hoặc DEMO từ web; bot từ chối file này.",
        )
        return
    if i.settings is None:
        b.add("runtime.mode", "Chế độ runtime", "unknown", "cấu hình .env chưa hợp lệ")
        return
    mode = effective_mode(i.settings, i.runtime)
    ceiling = env_ceiling(i.settings)
    asked = i.runtime.mode if i.runtime else None
    if asked is RuntimeMode.DEMO and ceiling is RuntimeMode.DRY_RUN:
        b.add(
            "runtime.mode",
            "Chế độ runtime",
            "warn",
            "file chọn DEMO nhưng .env chưa bật demo trading: bot chạy DRY-RUN",
            "Bật XAU_EDGE_ENABLE_DEMO_TRADING trong .env hoặc chuyển về DRY-RUN.",
        )
        return
    source = "runtime_mode.json" if i.runtime else ".env"
    b.add(
        "runtime.mode",
        "Chế độ runtime",
        "ok",
        f"{mode.value} (theo {source}; trần .env: {ceiling.value})",
    )


def _terminal_from_status(b: _Builder, i: PreflightInputs) -> None:
    st = i.status
    note = "bot đang chạy: không kết nối terminal (lock), đọc từ status.json"
    if st is None:
        b.add("mt5.connection", "Kết nối terminal", "unknown", note + " (chưa có status.json)")
    else:
        b.add(
            "mt5.connection",
            "Kết nối terminal",
            "ok" if st.connected else "fail",
            f"{note}: {'đã kết nối' if st.connected else 'mất kết nối'}",
        )
        demo = st.account_demo
        status: CheckStatus = "unknown" if demo is None else "ok" if demo else "fail"
        b.add(
            "mt5.trade_mode",
            "Trade mode DEMO",
            status,
            "DEMO" if demo else "không phải DEMO" if demo is False else "chưa biết",
        )
    for cid, label in (
        ("mt5.account", "Tài khoản trong whitelist"),
        ("mt5.server", "Server"),
        ("mt5.trade_allowed", "Terminal cho phép giao dịch"),
        ("mt5.password", "Loại mật khẩu đang dùng"),
    ):
        b.add(cid, label, "unknown", "bot đang chạy: sẽ kiểm tra khi bot dừng")


def _terminal_checks(b: _Builder, i: PreflightInputs) -> str | None:
    """Terminal checks; returns the masked account label when known."""
    t = i.terminal
    if t is None:
        _terminal_from_status(b, i)
        return None
    if not t.connected:
        status: CheckStatus = "unknown" if t.connected is None else "fail"
        hint = (
            "Cài gói MT5: uv sync --extra mt5 --extra api"
            if t.error == "MT5_PACKAGE_MISSING"
            else "Mở terminal FTMO MT5, đăng nhập tài khoản demo, rồi chạy lại."
        )
        b.add("mt5.connection", "Kết nối terminal", status, f"không kết nối được ({t.error})", hint)
        for cid, label in (
            ("mt5.account", "Tài khoản trong whitelist"),
            ("mt5.server", "Server"),
            ("mt5.trade_mode", "Trade mode DEMO"),
            ("mt5.trade_allowed", "Terminal cho phép giao dịch"),
            ("mt5.password", "Loại mật khẩu đang dùng"),
        ):
            b.add(cid, label, "unknown", "chưa kết nối terminal")
        return None
    b.add("mt5.connection", "Kết nối terminal", "ok", "đã kết nối (chỉ đọc, có timeout)")
    s = i.settings
    masked = mask_login(t.login) if t.login else "***"
    accounts = set(_csv(s.demo_allowed_accounts)) if s else set()
    on_list = bool(t.login) and t.login in accounts
    b.add(
        "mt5.account",
        "Tài khoản trong whitelist",
        "ok" if on_list else "warn",
        f"tài khoản {masked}: {'có' if on_list else 'không'} trong whitelist demo",
        "" if on_list else "DEMO cần login này trong XAU_EDGE_DEMO_ALLOWED_ACCOUNTS.",
    )
    servers = set(_csv(s.demo_allowed_servers)) if s else set()
    server_ok = not servers or (t.server or "") in servers
    b.add(
        "mt5.server",
        "Server",
        "ok" if server_ok else "warn",
        f"{t.server or 'không rõ'}" + ("" if server_ok else " (không có trong whitelist server)"),
    )
    demo = t.trade_mode_demo
    b.add(
        "mt5.trade_mode",
        "Trade mode DEMO",
        "ok" if demo else "fail" if demo is False else "unknown",
        "DEMO" if demo else "không phải DEMO" if demo is False else "chưa biết",
        "" if demo is not False else "Web chỉ dùng cho tài khoản DEMO.",
    )
    allowed = t.terminal_trade_allowed
    b.add(
        "mt5.trade_allowed",
        "Terminal cho phép giao dịch (Algo Trading)",
        "ok" if allowed else "warn" if allowed is False else "unknown",
        _yes(bool(allowed)) if allowed is not None else "chưa biết",
        "" if allowed else "Bật nút Algo Trading trong MT5 trước khi chuyển DEMO.",
    )
    trade = t.account_trade_allowed
    kind = "trade password" if trade else "investor password (chỉ đọc)" if trade is False else "?"
    b.add(
        "mt5.password",
        "Loại mật khẩu đang dùng",
        "ok" if trade is not None else "unknown",
        f"terminal đang đăng nhập bằng {kind}; bot DEMO đăng nhập lại bằng MT5_TRADE_PASSWORD",
    )
    prefix = "DEMO" if demo else "KHÔNG-DEMO" if demo is False else "?"
    return f"{prefix} {masked}"


def _ops_checks(b: _Builder, i: PreflightInputs) -> None:
    s = i.settings
    if s is None or s.news_calendar_path is None:
        b.add(
            "news.calendar",
            "Lịch tin",
            "warn",
            "chưa cấu hình: bot trả WAIT (NEWS_UNKNOWN)",
            "Đặt XAU_EDGE_NEWS_CALENDAR_PATH và chạy scripts/news_update.py.",
        )
    elif i.news_error or i.news_coverage_end is None:
        b.add(
            "news.calendar",
            "Lịch tin",
            "fail",
            "có đường dẫn nhưng không đọc được file",
            "Kiểm tra file lịch tin (dòng đầu '# coverage: ...').",
        )
    else:
        days = (i.news_coverage_end - i.now) / timedelta(days=1)
        status: CheckStatus = "ok" if days >= NEWS_MIN_DAYS else "warn"
        detail = f"còn {days:.1f} ngày coverage" if days > 0 else "coverage đã hết: bot sẽ WAIT"
        b.add(
            "news.calendar",
            "Lịch tin",
            status,
            detail,
            "" if status == "ok" else "Chạy scripts/news_update.py.",
        )
    pending = i.funded_pending
    b.add(
        "ftmo.rules",
        "Luật FTMO must_verify",
        "unknown" if pending is None else "warn" if pending else "ok",
        "không đọc được file luật"
        if pending is None
        else f"{pending} luật chưa xác minh (chỉ cảnh báo: đây là demo)"
        if pending
        else "đã xác minh hết",
    )
    tripped, reason = i.kill_switch
    b.add(
        "kill_switch",
        "Kill switch",
        "unknown" if tripped is None else "fail" if tripped else "ok",
        "không đọc được"
        if tripped is None
        else f"TRIPPED: {reason}"
        if tripped
        else "không tripped",
        f"Reset chỉ bằng CLI: {RESET_COMMAND}" if tripped else "",
    )
    p = i.process
    mode = i.status.mode if i.status and p.state is BotState.RUNNING else None
    b.add(
        "bot.process",
        "Tiến trình bot",
        "warn" if p.state is BotState.ERROR else "ok",
        f"{p.state.value}; lock: {'đang giữ' if p.pid else 'trống'}"
        + (f"; PID {p.pid}" if p.pid else "")
        + (f"; mode {mode}" if mode else "")
        + f"; backend {p.backend}"
        + (f" ({p.detail})" if p.state is BotState.ERROR else ""),
    )
    b.add(
        "nssm.service",
        "Dịch vụ NSSM",
        "ok",
        ("đã cài; --confirm-mode " + (i.nssm_confirm_mode or "không có (chỉ DRY-RUN)"))
        if i.nssm_installed
        else "chưa cài: web chạy bot như tiến trình con của API",
    )
    b.add(
        "files.writable",
        "Ghi được state/journal/status",
        "ok" if i.files_writable else "fail",
        "thư mục execution ghi được" if i.files_writable else "thư mục execution không ghi được",
        "" if i.files_writable else "Kiểm tra quyền thư mục data/execution.",
    )
    _freshness_check(b, i)
    off = i.clock_offset_seconds
    b.add(
        "clock.ntp",
        "Đồng hồ so với NTP",
        "unknown" if off is None else "fail" if abs(off) > i.max_clock_offset_seconds else "ok",
        "không đo được (không có NTP trả lời)" if off is None else f"lệch {off:+.2f} s",
        "Đồng bộ giờ Windows (w32tm /resync)."
        if off is not None and abs(off) > i.max_clock_offset_seconds
        else "",
    )
    v = i.strategy_validated
    b.add(
        "strategy",
        "Chiến lược VALIDATED",
        "unknown" if v is None else "ok" if v else "warn",
        "có" if v else "Không có edge được kiểm định: bot sẽ WAIT" if v is False else "chưa biết",
    )
    if i.token_protected is not None:
        b.add(
            "control.token",
            "Token điều khiển",
            "ok" if i.token_protected else "warn",
            "chỉ người dùng hiện tại đọc được"
            if i.token_protected
            else "không siết được quyền file token",
        )


def _freshness_check(b: _Builder, i: PreflightInputs) -> None:
    st = i.status
    if st is None:
        b.add("data.freshness", "Dữ liệu mới nhất", "unknown", "chưa có status.json")
        return
    age = (i.now - st.updated_at) / timedelta(minutes=1)
    data_age = st.last_cycle.data_age_minutes if st.last_cycle else None
    detail = f"status cập nhật {age:.0f} phút trước" + (
        f"; dữ liệu chu kỳ cuối cũ {data_age:.0f} phút" if data_age is not None else ""
    )
    running = i.process.state is BotState.RUNNING
    stale = running and age > STATUS_STALE_MINUTES
    b.add("data.freshness", "Dữ liệu mới nhất", "warn" if stale else "ok", detail)


def _demo_blockers(i: PreflightInputs) -> tuple[list[Blocker], list[str]]:
    out: list[Blocker] = []
    unverified: list[str] = []
    s = i.settings
    if s is None:
        return [Blocker(code="ENV_INVALID", message=".env chưa hợp lệ")], unverified
    if s.enable_funded_trading:
        out.append(Blocker(code="FUNDED_CONFIGURED", message="FUNDED đang bật trong .env"))
    if not s.enable_demo_trading:
        out.append(
            Blocker(code="ENV_DEMO_DISABLED", message=".env chưa bật XAU_EDGE_ENABLE_DEMO_TRADING")
        )
    for flag, code, message in (
        (
            bool(_csv(s.demo_allowed_accounts)),
            "ENV_NO_ACCOUNT_WHITELIST",
            "thiếu whitelist tài khoản",
        ),
        (s.demo_magic is not None, "ENV_NO_MAGIC", "thiếu XAU_EDGE_DEMO_MAGIC"),
        (s.demo_initial_capital is not None, "ENV_NO_INITIAL_CAPITAL", "thiếu vốn ban đầu demo"),
        (SYMBOL in _csv(s.demo_allowed_symbols), "ENV_SYMBOL", "XAUUSD không trong whitelist"),
    ):
        if not flag:
            out.append(Blocker(code=code, message=message))
    c = i.credentials
    if not (c.has_trade_password and c.has_login and c.has_server):
        out.append(
            Blocker(
                code="NO_TRADE_PASSWORD", message="thiếu MT5_TRADE_PASSWORD/MT5_LOGIN/MT5_SERVER"
            )
        )
    t = i.terminal
    if t is None or not t.connected:
        unverified.append("tài khoản, trade mode và Algo Trading của terminal")
    else:
        accounts = set(_csv(s.demo_allowed_accounts))
        if not t.login or t.login not in accounts:
            out.append(
                Blocker(
                    code="ACCOUNT_NOT_WHITELISTED",
                    message="tài khoản terminal không trong whitelist demo",
                )
            )
        if t.trade_mode_demo is False:
            out.append(
                Blocker(code="NOT_DEMO_ACCOUNT", message="terminal không phải tài khoản DEMO")
            )
        if not t.terminal_trade_allowed:
            out.append(
                Blocker(code="TERMINAL_TRADE_DISABLED", message="terminal chưa bật Algo Trading")
            )
    if i.kill_switch[0]:
        out.append(Blocker(code="KILL_SWITCH_TRIPPED", message="kill switch đang tripped"))
    return out, unverified


def build_report(i: PreflightInputs) -> PreflightReport:
    """All checks, the F3 blockers and the banner facts."""
    b = _Builder()
    _env_checks(b, i)
    _runtime_check(b, i)
    label = _terminal_checks(b, i)
    _ops_checks(b, i)
    counts = {
        s: sum(1 for c in b.checks if c.status == s) for s in ("ok", "warn", "fail", "unknown")
    }
    blockers, unverified = _demo_blockers(i)
    failing = [c.id for c in b.checks if c.status == "fail"]
    if failing:
        blockers.append(
            Blocker(code="PREFLIGHT_FAIL", message="preflight có mục fail: " + ", ".join(failing))
        )
    source: TerminalSource = (
        "terminal" if i.terminal is not None else "status.json" if i.status else "none"
    )
    s = i.settings
    return PreflightReport(
        generated_at=i.now,
        checks=b.checks,
        has_fail=bool(failing),
        counts=counts,
        terminal_source=source,
        account_label=label,
        strategy_validated=i.strategy_validated,
        configured_mode=effective_mode(s, i.runtime) if s else RuntimeMode.DRY_RUN,
        mode_ceiling=env_ceiling(s) if s else RuntimeMode.DRY_RUN,
        demo_blockers=blockers,
        demo_unverified=unverified,
        smoke_enabled=bool(s and s.demo_smoke),
    )


# -- the terminal probe -------------------------------------------------------------------------


def _probe_once(load_mt5: Callable[[], Any], terminal_path: str, timeout_ms: int) -> RawTerminal:
    mt5 = QueryOnlyMt5(load_mt5())
    if not mt5.initialize(path=terminal_path, timeout=timeout_ms):
        return RawTerminal(connected=False, error="INITIALIZE_FAILED")
    try:
        term = mt5.terminal_info()
        acc = mt5.account_info()
        if acc is None:
            return RawTerminal(connected=False, error="NO_ACCOUNT_LOGGED_IN")
        return RawTerminal(
            connected=True,
            login=str(acc.login),
            server=str(getattr(acc, "server", "")) or None,
            trade_mode_demo=acc.trade_mode == mt5.ACCOUNT_TRADE_MODE_DEMO,
            terminal_trade_allowed=bool(getattr(term, "trade_allowed", False)) if term else None,
            account_trade_allowed=bool(getattr(acc, "trade_allowed", False)),
        )
    finally:
        mt5.shutdown()


def probe_terminal(
    load_mt5: Callable[[], Any],
    terminal_path: str,
    *,
    timeout_seconds: float = 20.0,
    margin_seconds: float = 5.0,
) -> RawTerminal:
    """Read-only look at the terminal, never longer than ``timeout_seconds`` (+ a margin)."""
    box: list[RawTerminal] = []

    def work() -> None:
        try:
            box.append(_probe_once(load_mt5, terminal_path, int(timeout_seconds * 1000)))
        except ImportError:
            box.append(RawTerminal(connected=False, error="MT5_PACKAGE_MISSING"))
        except Exception as exc:
            name = type(exc).__name__
            missing = "NotAvailable" in name
            box.append(
                RawTerminal(connected=False, error="MT5_PACKAGE_MISSING" if missing else name)
            )

    thread = threading.Thread(target=work, name="mt5-preflight", daemon=True)
    thread.start()
    thread.join(timeout_seconds + margin_seconds)
    return box[0] if box else RawTerminal(connected=None, error="TIMEOUT")
