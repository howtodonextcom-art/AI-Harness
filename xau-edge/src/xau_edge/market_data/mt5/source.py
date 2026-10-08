"""MetaTrader 5 market-data source (read-only, demo accounts only).

This module only reads historical bars. It deliberately exposes no position or order
functionality; execution lives behind a separate, disabled-by-default interface. Three
independent controls enforce that:

* the client is wrapped in :class:`ReadOnlyMt5Client`, an allowlist proxy that makes every
  other function of the MetaTrader5 module unreachable (not merely unused);
* every connection and every fetch is refused unless the logged-in account is a DEMO account;
* a test fails if source or scripts touch any MT5 attribute outside the allowlist.

Time handling (important): the terminal reports bar times as *broker server wall-clock*
labelled as if it were UTC. ``broker_timezone`` is therefore mandatory, and is used both to
shift request bounds into server wall-clock and to convert returned times back to true UTC.
The conversion was verified against a live FTMO demo terminal (see
``docs/reports/mt5-verification.md``): for that server the clock is ``NY+7``.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

import polars as pl
from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from xau_edge.domain.bars import BarRequest, coerce_bars, empty_bars
from xau_edge.market_data.broker_clock import BrokerClock


class Mt5NotAvailableError(RuntimeError):
    """Raised when the MetaTrader5 package cannot be imported."""


class Mt5AccountError(RuntimeError):
    """Raised when the connected MT5 account is not a DEMO account."""


class Mt5Settings(BaseSettings):
    """MT5 connection settings from ``MT5_*`` environment variables or ``.env``."""

    model_config = SettingsConfigDict(
        env_prefix="MT5_", env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    login: int | None = None
    password: SecretStr | None = None
    server: str | None = None
    terminal_path: Path | None = None
    broker_timezone: str | None = None


class Mt5Client(Protocol):
    """The subset of the MetaTrader5 module used for market data."""

    def initialize(self, **kwargs: Any) -> bool: ...

    def shutdown(self) -> None: ...

    def last_error(self) -> tuple[int, str]: ...

    def account_info(self) -> Any: ...

    def copy_rates_range(
        self, symbol: str, timeframe: int, start: datetime, end: datetime
    ) -> Any: ...


_ALLOWED_MT5_NAMES = frozenset(
    {
        "initialize",
        "shutdown",
        "last_error",
        "account_info",
        "copy_rates_range",
        "ACCOUNT_TRADE_MODE_DEMO",
    }
)


class ReadOnlyMt5Client:
    """Allowlist proxy over the MetaTrader5 module.

    Only market-data calls, the account-type check and ``TIMEFRAME_*`` constants are reachable
    through normal attribute access. Everything else (orders, positions, history deals, login, ...)
    raises ``AttributeError``, which prevents accidental or buggy use.

    This is NOT a sandbox: Python cannot hide the wrapped object from code running in the same
    process (``proxy._inner`` is reachable). The controls that matter against deliberate misuse
    are the DEMO-account guard, the terminal\'s own trading switch, and using the MT5 *investor*
    (read-only) password.
    """

    def __init__(self, client: Mt5Client) -> None:
        self._inner = client

    def __getattr__(self, name: str) -> Any:
        if name in _ALLOWED_MT5_NAMES or name.startswith("TIMEFRAME_"):
            return getattr(self._inner, name)
        msg = f"{name!r} is not available: this MT5 client is read-only (market data only)"
        raise AttributeError(msg)


def load_mt5_module() -> Any:
    """Import the ``MetaTrader5`` package or raise an actionable error."""
    try:
        import MetaTrader5  # noqa: PLC0415 - optional, Windows-only dependency
    except ImportError as exc:
        msg = (
            "The MetaTrader5 package is not installed (it is Windows-only). "
            "Install it with: pip install 'xau-edge[mt5]'"
        )
        raise Mt5NotAvailableError(msg) from exc
    return MetaTrader5


def _utc_now() -> datetime:
    return datetime.now(UTC)


class Mt5BarSource:
    """Fetch historical bars from a locally running MetaTrader 5 DEMO terminal."""

    name = "mt5"

    def __init__(
        self,
        client: Mt5Client,
        settings: Mt5Settings,
        *,
        now: Callable[[], datetime] = _utc_now,
    ) -> None:
        if not settings.broker_timezone:
            msg = (
                "broker_timezone is required (set MT5_BROKER_TIMEZONE to the broker's "
                "server clock, e.g. 'NY+7' or an IANA zone); MT5 timestamps cannot be "
                "interpreted without it"
            )
            raise ValueError(msg)
        self._client = ReadOnlyMt5Client(client)
        self._settings = settings
        self._clock = BrokerClock.parse(settings.broker_timezone)
        self._now = now

    def connect(self) -> None:
        """Initialise the terminal connection (market data only, DEMO accounts only)."""
        s = self._settings
        kwargs: dict[str, Any] = {}
        if s.terminal_path is not None:
            kwargs["path"] = str(s.terminal_path)
        if s.login is not None:
            kwargs["login"] = s.login
        if s.password is not None:
            kwargs["password"] = s.password.get_secret_value()
        if s.server is not None:
            kwargs["server"] = s.server
        if not self._client.initialize(**kwargs):
            msg = f"MT5 initialize failed: {self._client.last_error()}"
            raise RuntimeError(msg)
        try:
            self._require_demo()
        except BaseException:
            self._client.shutdown()  # never leave a possibly-live terminal initialised
            raise

    def close(self) -> None:
        """Shut the terminal connection down."""
        self._client.shutdown()

    def fetch_bars(self, request: BarRequest) -> pl.DataFrame:
        """Return complete bars in ``[request.start, request.end)`` with UTC open timestamps.

        The bar still forming at call time is never returned: its OHLC and volume are partial.
        """
        self._require_demo()
        constant = getattr(self._client, f"TIMEFRAME_{request.timeframe.value}", None)
        if constant is None:
            msg = f"MT5 client has no constant for timeframe {request.timeframe.value}"
            raise RuntimeError(msg)

        start_wall = self._to_server_wall_clock(request.start_utc)
        end_wall = self._to_server_wall_clock(request.end_utc)
        rates = self._client.copy_rates_range(request.symbol, constant, start_wall, end_wall)
        if rates is None:
            msg = f"MT5 copy_rates_range failed: {self._client.last_error()}"
            raise RuntimeError(msg)
        if len(rates) == 0:
            return empty_bars()

        frame = pl.DataFrame(
            {
                "timestamp": self._to_utc(pl.Series(rates["time"])),
                "open": rates["open"],
                "high": rates["high"],
                "low": rates["low"],
                "close": rates["close"],
                "tick_volume": rates["tick_volume"].astype("int64"),
                "spread": rates["spread"].astype("int64"),
                "real_volume": rates["real_volume"].astype("int64"),
            }
        )
        out = coerce_bars(frame)
        closes_at = pl.col("timestamp") + pl.duration(minutes=request.timeframe.minutes)
        return out.filter(
            (pl.col("timestamp") >= request.start_utc)
            & (pl.col("timestamp") < request.end_utc)
            & (closes_at <= self._now())
        )

    def _require_demo(self) -> None:
        """Refuse to read from anything but a DEMO account (a live password also trades)."""
        info = self._client.account_info()
        if info is None or info.trade_mode != self._client.ACCOUNT_TRADE_MODE_DEMO:
            msg = (
                "refusing to use MT5: the connected account is not a DEMO account "
                "(or no account is logged in)"
            )
            raise Mt5AccountError(msg)

    def _to_server_wall_clock(self, utc_dt: datetime) -> datetime:
        """True UTC instant -> broker wall clock, labelled UTC (what MT5 expects)."""
        return self._clock.label_as_utc(utc_dt)

    def _to_utc(self, epoch_seconds: pl.Series) -> pl.Series:
        """Server-wall-clock epoch seconds -> true UTC datetimes (ambiguity raises)."""
        naive = pl.from_epoch(epoch_seconds, time_unit="s").cast(pl.Datetime("us"))
        return self._clock.server_to_utc(naive)


__all__ = [
    "Mt5AccountError",
    "Mt5BarSource",
    "Mt5Client",
    "Mt5NotAvailableError",
    "Mt5Settings",
    "ReadOnlyMt5Client",
    "load_mt5_module",
]
