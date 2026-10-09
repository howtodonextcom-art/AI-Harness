from __future__ import annotations

import ast
import builtins
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import numpy as np
import pytest

from xau_edge.domain.bars import BarRequest
from xau_edge.domain.timeframe import Timeframe
from xau_edge.market_data.mt5.source import (
    Mt5AccountError,
    Mt5BarSource,
    Mt5NotAvailableError,
    Mt5Settings,
    ReadOnlyMt5Client,
    load_mt5_module,
)

pytestmark = pytest.mark.unit

RATE_DTYPE = np.dtype(
    [
        ("time", "<i8"),
        ("open", "<f8"),
        ("high", "<f8"),
        ("low", "<f8"),
        ("close", "<f8"),
        ("tick_volume", "<u8"),
        ("spread", "<i4"),
        ("real_volume", "<u8"),
    ]
)


class FakeMt5:
    """Stand-in for the MetaTrader5 module.

    Like the real ``copy_rates_range`` it honours its bounds (inclusive on both ends), and like
    the real module it exposes trading functions, so tests can prove they are unreachable.
    """

    TIMEFRAME_M1 = 1
    TIMEFRAME_M5 = 5
    TIMEFRAME_M15 = 15
    TIMEFRAME_M30 = 30
    TIMEFRAME_H1 = 16385
    TIMEFRAME_H4 = 16388
    ACCOUNT_TRADE_MODE_DEMO = 0
    ACCOUNT_TRADE_MODE_CONTEST = 1
    ACCOUNT_TRADE_MODE_REAL = 2

    def __init__(
        self,
        rates: np.ndarray[Any, Any] | None,
        *,
        trade_mode: int | None = ACCOUNT_TRADE_MODE_DEMO,
    ) -> None:
        self.rates = rates
        self.trade_mode = trade_mode
        self.calls: list[tuple[str, Any]] = []
        self.shut_down = False

    def initialize(self, **kwargs: Any) -> bool:
        self.calls.append(("initialize", kwargs))
        return True

    def shutdown(self) -> None:
        self.shut_down = True

    def last_error(self) -> tuple[int, str]:
        return (1, "fake error")

    def account_info(self) -> Any:
        if self.trade_mode is None:
            return None
        return SimpleNamespace(trade_mode=self.trade_mode)

    def order_send(self, *args: Any, **kwargs: Any) -> Any:
        msg = "order_send must never be reachable from market-data code"
        raise AssertionError(msg)

    def copy_rates_range(self, symbol: str, tf: int, start: datetime, end: datetime) -> Any:
        self.calls.append(("copy_rates_range", (symbol, tf, start, end)))
        if self.rates is None:
            return None
        times = self.rates["time"]
        keep = (times >= int(start.timestamp())) & (times <= int(end.timestamp()))
        return self.rates[keep]


def rates_from_server_wall_clock(*wall: datetime) -> np.ndarray[Any, Any]:
    """MT5 labels broker wall-clock time as if it were UTC epoch seconds."""
    arr = np.zeros(len(wall), dtype=RATE_DTYPE)
    for i, w in enumerate(wall):
        arr[i] = (int(w.replace(tzinfo=UTC).timestamp()), 2000.0, 2001.0, 1999.0, 2000.5, 10, 20, 0)
    return arr


def request() -> BarRequest:
    return BarRequest(
        symbol="XAUUSD",
        timeframe=Timeframe.M15,
        start=datetime(2025, 3, 3, 0, 0, tzinfo=UTC),
        end=datetime(2025, 3, 3, 6, 0, tzinfo=UTC),
    )


def test_broker_timezone_is_required(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MT5_BROKER_TIMEZONE", raising=False)
    with pytest.raises(ValueError, match="broker_timezone"):
        Mt5BarSource(FakeMt5(None), Mt5Settings(_env_file=None))


def test_server_wall_clock_is_converted_to_utc() -> None:
    # Broker in Athens (UTC+2 in March): server wall 02:00 == 00:00 UTC.
    fake = FakeMt5(
        rates_from_server_wall_clock(
            datetime(2025, 3, 3, 2, 0),  # noqa: DTZ001
            datetime(2025, 3, 3, 2, 15),  # noqa: DTZ001
        )
    )
    src = Mt5BarSource(fake, Mt5Settings(broker_timezone="Europe/Athens"))
    df = src.fetch_bars(request())
    assert df["timestamp"].to_list() == [
        datetime(2025, 3, 3, 0, 0, tzinfo=UTC),
        datetime(2025, 3, 3, 0, 15, tzinfo=UTC),
    ]
    assert df["tick_volume"].dtype.is_integer()


def test_request_bounds_are_shifted_into_server_wall_clock() -> None:
    fake = FakeMt5(rates_from_server_wall_clock(datetime(2025, 3, 3, 2, 0)))  # noqa: DTZ001
    Mt5BarSource(fake, Mt5Settings(broker_timezone="Europe/Athens")).fetch_bars(request())
    name, (symbol, tf, start, end) = fake.calls[-1]
    assert name == "copy_rates_range"
    assert (symbol, tf) == ("XAUUSD", FakeMt5.TIMEFRAME_M15)
    # 00:00 UTC is 02:00 in Athens; MT5 expects that wall clock labelled as UTC.
    assert start == datetime(2025, 3, 3, 2, 0, tzinfo=UTC)
    assert end == datetime(2025, 3, 3, 8, 0, tzinfo=UTC)


@pytest.mark.parametrize(
    ("tf", "const"),
    [
        (Timeframe.M5, 5),
        (Timeframe.M15, 15),
        (Timeframe.H1, 16385),
        (Timeframe.H4, 16388),
    ],
)
def test_timeframe_constants_are_mapped(tf: Timeframe, const: int) -> None:
    fake = FakeMt5(rates_from_server_wall_clock(datetime(2025, 3, 3, 2, 0)))  # noqa: DTZ001
    req = request().model_copy(update={"timeframe": tf})
    Mt5BarSource(fake, Mt5Settings(broker_timezone="Europe/Athens")).fetch_bars(req)
    assert fake.calls[-1][1][1] == const


def test_none_result_raises_with_terminal_error() -> None:
    src = Mt5BarSource(FakeMt5(None), Mt5Settings(broker_timezone="Europe/Athens"))
    with pytest.raises(RuntimeError, match="fake error"):
        src.fetch_bars(request())


def test_empty_result_returns_empty_frame() -> None:
    fake = FakeMt5(np.zeros(0, dtype=RATE_DTYPE))
    out = Mt5BarSource(fake, Mt5Settings(broker_timezone="Europe/Athens")).fetch_bars(request())
    assert out.height == 0


def test_connect_passes_credentials_and_close_shuts_down() -> None:
    fake = FakeMt5(None)
    settings = Mt5Settings(
        broker_timezone="UTC",
        login=123,
        password="s3cret",
        server="Demo-Server",
    )
    src = Mt5BarSource(fake, settings)
    src.connect()
    kwargs = fake.calls[0][1]
    assert kwargs["login"] == 123
    assert kwargs["server"] == "Demo-Server"
    assert kwargs["password"] == "s3cret"
    src.close()
    assert fake.shut_down


def test_password_is_not_leaked_in_repr() -> None:
    settings = Mt5Settings(broker_timezone="UTC", password="s3cret")
    assert "s3cret" not in repr(settings)
    assert "s3cret" not in str(settings)


def test_missing_package_gives_actionable_error(monkeypatch: pytest.MonkeyPatch) -> None:
    real_import = builtins.__import__

    def fake_import(name: str, *args: Any, **kwargs: Any) -> Any:
        if name == "MetaTrader5":
            raise ImportError("no module")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    with pytest.raises(Mt5NotAvailableError, match="xau-edge\\[mt5\\]"):
        load_mt5_module()


def test_load_mt5_module_returns_the_real_package_when_installed() -> None:
    real = pytest.importorskip("MetaTrader5")
    assert load_mt5_module() is real


def test_connect_passes_terminal_path() -> None:
    fake = FakeMt5(None)
    settings = Mt5Settings(broker_timezone="UTC", terminal_path=Path("C:/mt5/terminal64.exe"))
    Mt5BarSource(fake, settings).connect()
    assert fake.calls[0][1]["path"] == str(Path("C:/mt5/terminal64.exe"))


def test_fake_client_constants_match_the_real_module() -> None:
    """Guards the fake against drifting from MetaTrader5 (skipped if the package is absent)."""
    real = pytest.importorskip("MetaTrader5")
    for tf in Timeframe:
        name = f"TIMEFRAME_{tf.value}"
        assert getattr(real, name) == getattr(FakeMt5, name), name
    for name in (
        "ACCOUNT_TRADE_MODE_DEMO",
        "ACCOUNT_TRADE_MODE_CONTEST",
        "ACCOUNT_TRADE_MODE_REAL",
    ):
        assert getattr(real, name) == getattr(FakeMt5, name), name
    assert callable(real.copy_rates_range)
    assert callable(real.account_info)


def test_mt5_package_contains_no_trading_calls() -> None:
    """Safety: the MT5 adapter is market-data only. No order/position API may be referenced."""
    forbidden = {"order_send", "order_check", "positions_get", "orders_get", "order_calc_margin"}
    root = Path(__file__).resolve().parents[3] / "src" / "xau_edge" / "market_data" / "mt5"
    seen: set[str] = set()
    for path in root.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute):
                seen.add(node.attr)
            elif isinstance(node, ast.Name):
                seen.add(node.id)
            elif isinstance(node, ast.Constant) and isinstance(node.value, str):
                seen.add(node.value)
    assert not (forbidden & seen)


# --- Sprint 3 remediation (ECC review findings F-03, F-04, F-05, F-13) -----------------------

ATHENS = Mt5Settings(broker_timezone="Europe/Athens")
ALLOWED_MT5_ATTRIBUTES = {
    "initialize",
    "shutdown",
    "last_error",
    "copy_rates_range",
    "account_info",
    "terminal_info",
    "symbol_select",
    "symbol_info_tick",
    "trade_allowed",
    "ACCOUNT_TRADE_MODE_DEMO",
    # read-only market-data names (MT5 data platform): none of them can place, modify or close
    # anything; orders, positions, deals and trade history are deliberately absent.
    "version",
    "symbols_get",
    "symbol_info",
    "copy_rates_from_pos",
    "copy_rates_from",
    "copy_ticks_range",
    "copy_ticks_from",
    "COPY_TICKS_ALL",
    "COPY_TICKS_INFO",
    "COPY_TICKS_TRADE",
}


def wall(hour: int, minute: int = 0) -> datetime:
    """Naive server wall-clock on 2025-03-03 (Athens is UTC+2 that day)."""
    return datetime(2025, 3, 3, hour, minute)  # noqa: DTZ001


@pytest.mark.parametrize(
    "mode",
    [FakeMt5.ACCOUNT_TRADE_MODE_CONTEST, FakeMt5.ACCOUNT_TRADE_MODE_REAL, None],
    ids=["contest", "real", "no-account"],
)
def test_connect_refuses_anything_but_a_demo_account_and_shuts_down(mode: int | None) -> None:
    fake = FakeMt5(None, trade_mode=mode)
    with pytest.raises(Mt5AccountError, match="DEMO"):
        Mt5BarSource(fake, ATHENS).connect()
    assert fake.shut_down


@pytest.mark.parametrize("mode", [FakeMt5.ACCOUNT_TRADE_MODE_REAL, None], ids=["real", "none"])
def test_fetch_bars_also_refuses_non_demo_accounts_without_connect(mode: int | None) -> None:
    fake = FakeMt5(rates_from_server_wall_clock(wall(2)), trade_mode=mode)
    with pytest.raises(Mt5AccountError):
        Mt5BarSource(fake, ATHENS).fetch_bars(request())
    assert not [c for c in fake.calls if c[0] == "copy_rates_range"]


def test_the_demo_check_is_on_by_default_and_only_the_funded_bot_turns_it_off() -> None:
    fake = FakeMt5(
        rates_from_server_wall_clock(wall(2)), trade_mode=FakeMt5.ACCOUNT_TRADE_MODE_REAL
    )
    with pytest.raises(Mt5AccountError):
        Mt5BarSource(fake, ATHENS).fetch_bars(request())
    funded = Mt5BarSource(fake, ATHENS, require_demo=False)
    assert funded.fetch_bars(request()).height == 1
    assert isinstance(funded._client, ReadOnlyMt5Client)  # still market data only
    with pytest.raises(AttributeError):
        funded._client.order_send  # noqa: B018


def test_connect_shuts_the_terminal_down_on_any_failure_during_the_account_check() -> None:
    """Re-review: a crash while inspecting the account must not leave the terminal initialised."""

    class Exploding(FakeMt5):
        def account_info(self) -> Any:
            msg = "boom"
            raise RuntimeError(msg)

    fake = Exploding(None)
    with pytest.raises(RuntimeError, match="boom"):
        Mt5BarSource(fake, ATHENS).connect()
    assert fake.shut_down


def test_demo_account_is_accepted() -> None:
    fake = FakeMt5(rates_from_server_wall_clock(wall(2)))
    assert Mt5BarSource(fake, ATHENS).fetch_bars(request()).height == 1


def test_read_only_client_blocks_trading_functions_and_allows_market_data() -> None:
    proxy = ReadOnlyMt5Client(FakeMt5(None))
    for blocked in ("order_send", "positions_get", "orders_get", "history_deals_get", "login"):
        with pytest.raises(AttributeError, match="read-only"):
            getattr(proxy, blocked)
    assert proxy.TIMEFRAME_M15 == FakeMt5.TIMEFRAME_M15
    assert proxy.ACCOUNT_TRADE_MODE_DEMO == FakeMt5.ACCOUNT_TRADE_MODE_DEMO
    assert callable(proxy.copy_rates_range)
    assert callable(proxy.account_info)


def test_bar_source_only_ever_holds_the_read_only_proxy() -> None:
    src = Mt5BarSource(FakeMt5(None), ATHENS)
    assert isinstance(src._client, ReadOnlyMt5Client)
    with pytest.raises(AttributeError):
        src._client.order_send  # noqa: B018


def test_mt5_attributes_used_by_src_and_scripts_are_on_the_allowlist() -> None:
    project = Path(__file__).resolve().parents[3]
    used: set[str] = set()
    for root in (project / "src", project / "scripts"):
        for path in root.rglob("*.py"):
            if "brokers" in path.parts:
                continue  # the demo adapter has its own, stricter test (tests/unit/brokers)
            for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
                if not isinstance(node, ast.Attribute):
                    continue
                base = node.value
                on_client = (isinstance(base, ast.Name) and base.id in {"mt5", "MetaTrader5"}) or (
                    isinstance(base, ast.Attribute) and base.attr == "_client"
                )
                if on_client:
                    used.add(node.attr)
    unexpected = {
        u for u in used if u not in ALLOWED_MT5_ATTRIBUTES and not u.startswith("TIMEFRAME_")
    }
    assert not unexpected, f"MT5 attributes outside the read-only allowlist: {sorted(unexpected)}"


def test_forming_bar_is_dropped_and_a_just_closed_bar_is_kept() -> None:
    rates = rates_from_server_wall_clock(wall(2, 0), wall(2, 15), wall(2, 30))  # UTC 00:00/15/30
    fixed_now = datetime(2025, 3, 3, 0, 40, tzinfo=UTC)
    src = Mt5BarSource(FakeMt5(rates), ATHENS, now=lambda: fixed_now)
    out = src.fetch_bars(request())
    # The 00:30 bar closes at 00:45, which is after "now": it is still forming.
    assert out["timestamp"].to_list() == [
        datetime(2025, 3, 3, 0, 0, tzinfo=UTC),
        datetime(2025, 3, 3, 0, 15, tzinfo=UTC),
    ]
    at_close = datetime(2025, 3, 3, 0, 45, tzinfo=UTC)
    out2 = Mt5BarSource(FakeMt5(rates), ATHENS, now=lambda: at_close).fetch_bars(request())
    assert out2.height == 3  # a bar that closes exactly now is complete


def test_request_start_is_inclusive_and_end_is_exclusive() -> None:
    # Request: 00:00-06:00 UTC == server wall 02:00-08:00 (the fake returns both bounds).
    rates = rates_from_server_wall_clock(wall(1, 45), wall(2, 0), wall(7, 45), wall(8, 0))
    out = Mt5BarSource(FakeMt5(rates), ATHENS).fetch_bars(request())
    assert out["timestamp"].to_list() == [
        datetime(2025, 3, 3, 0, 0, tzinfo=UTC),  # start inclusive
        datetime(2025, 3, 3, 5, 45, tzinfo=UTC),  # last bar before end
    ]  # the bar at exactly 06:00 UTC (end) is excluded
