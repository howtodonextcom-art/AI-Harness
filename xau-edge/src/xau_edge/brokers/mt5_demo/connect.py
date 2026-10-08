"""Connect the terminal with TRADING credentials, for the demo executor only (ADR-0019).

Data-only scripts use the investor (read-only) password through ``MT5_PASSWORD``. Order sending
needs the trading password, kept in a different variable (``MT5_TRADE_PASSWORD``) so the two can
never be mixed up. The password is never printed or logged, and after connecting the account is
checked to be a DEMO account; anything else shuts the terminal connection down again.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from xau_edge.brokers.mt5_demo.reader import DemoAccountError, DemoReader


class TradeConnectError(RuntimeError):
    """The trading connection could not be made safely."""


class Mt5TradeSettings(BaseSettings):
    """Trading credentials from ``MT5_*`` environment variables or ``.env``."""

    model_config = SettingsConfigDict(
        env_prefix="MT5_", env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    login: int | None = None
    trade_password: SecretStr | None = None
    server: str | None = None


def connect_for_trading(
    mt5: Any, reader: DemoReader, terminal_path: str, settings: Mt5TradeSettings | None = None
) -> None:
    """Initialise the terminal with the trading password and confirm it is a DEMO account."""
    creds = settings or Mt5TradeSettings()
    if creds.login is None or creds.trade_password is None or not creds.server:
        msg = "MT5_LOGIN, MT5_TRADE_PASSWORD and MT5_SERVER must all be set to send demo orders"
        raise TradeConnectError(msg)
    ok = mt5.initialize(
        path=str(Path(terminal_path)),
        login=creds.login,
        password=creds.trade_password.get_secret_value(),
        server=creds.server,
        timeout=90000,
    )
    if not ok:
        msg = f"MT5 initialize with the trading login failed: {mt5.last_error()}"
        raise TradeConnectError(msg)
    try:
        account = reader.account()
    except DemoAccountError as exc:
        mt5.shutdown()
        raise TradeConnectError(str(exc)) from exc
    if not account.trade_allowed:
        mt5.shutdown()
        msg = "the account still does not allow trading (investor login or trading disabled)"
        raise TradeConnectError(msg)
