"""MetaTrader 5 market-data source (read-only).

This module only reads historical bars. It deliberately exposes no account, position or
order functionality; execution lives behind a separate, disabled-by-default interface.

Time handling (important): the terminal reports bar times as *broker server wall-clock*
labelled as if it were UTC. ``broker_timezone`` is therefore mandatory, and is used both to
shift request bounds into server wall-clock and to convert returned times back to true UTC.
This conversion is covered by unit tests with a fake client but has NOT yet been verified
against a live terminal.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Protocol

import polars as pl
from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from xau_edge.domain.bars import BarRequest, coerce_bars, empty_bars
from xau_edge.market_data.broker_clock import BrokerClock


class Mt5NotAvailableError(RuntimeError):
    """Raised when the MetaTrader5 package cannot be imported."""


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

    def copy_rates_range(
        self, symbol: str, timeframe: int, start: datetime, end: datetime
    ) -> Any: ...


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


class Mt5BarSource:
    """Fetch historical bars from a locally running MetaTrader 5 terminal."""

    name = "mt5"

    def __init__(self, client: Mt5Client, settings: Mt5Settings) -> None:
        if not settings.broker_timezone:
            msg = (
                "broker_timezone is required (set MT5_BROKER_TIMEZONE to the broker's "
                "server IANA timezone); MT5 timestamps cannot be interpreted without it"
            )
            raise ValueError(msg)
        self._client = client
        self._settings = settings
        self._clock = BrokerClock.parse(settings.broker_timezone)

    def connect(self) -> None:
        """Initialise the terminal connection (market data only)."""
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

    def close(self) -> None:
        """Shut the terminal connection down."""
        self._client.shutdown()

    def fetch_bars(self, request: BarRequest) -> pl.DataFrame:
        """Return bars in ``[request.start, request.end)`` with UTC bar-open timestamps."""
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
        return out.filter(
            (pl.col("timestamp") >= request.start_utc) & (pl.col("timestamp") < request.end_utc)
        )

    def _to_server_wall_clock(self, utc_dt: datetime) -> datetime:
        """True UTC instant -> broker wall clock, labelled UTC (what MT5 expects)."""
        return self._clock.label_as_utc(utc_dt)

    def _to_utc(self, epoch_seconds: pl.Series) -> pl.Series:
        """Server-wall-clock epoch seconds -> true UTC datetimes (ambiguity raises)."""
        naive = pl.from_epoch(epoch_seconds, time_unit="s").cast(pl.Datetime("us"))
        return self._clock.server_to_utc(naive)


__all__ = [
    "Mt5BarSource",
    "Mt5Client",
    "Mt5NotAvailableError",
    "Mt5Settings",
    "load_mt5_module",
]
