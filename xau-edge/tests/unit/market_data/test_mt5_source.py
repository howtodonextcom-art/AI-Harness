from __future__ import annotations

import ast
import builtins
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from xau_edge.domain.bars import BarRequest
from xau_edge.domain.timeframe import Timeframe
from xau_edge.market_data.mt5.source import (
    Mt5BarSource,
    Mt5NotAvailableError,
    Mt5Settings,
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
    """Minimal stand-in for the MetaTrader5 module (market-data calls only)."""

    TIMEFRAME_M5 = 5
    TIMEFRAME_M15 = 15
    TIMEFRAME_H1 = 16385
    TIMEFRAME_H4 = 16388

    def __init__(self, rates: np.ndarray[Any, Any] | None) -> None:
        self.rates = rates
        self.calls: list[tuple[str, Any]] = []
        self.shut_down = False

    def initialize(self, **kwargs: Any) -> bool:
        self.calls.append(("initialize", kwargs))
        return True

    def shutdown(self) -> None:
        self.shut_down = True

    def last_error(self) -> tuple[int, str]:
        return (1, "fake error")

    def copy_rates_range(self, symbol: str, tf: int, start: datetime, end: datetime) -> Any:
        self.calls.append(("copy_rates_range", (symbol, tf, start, end)))
        return self.rates


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
    assert callable(real.copy_rates_range)


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
