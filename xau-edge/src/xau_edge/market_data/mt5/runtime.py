"""Open a read-only MT5 feed on the local terminal (the only place that calls ``initialize``)."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from xau_edge.market_data.broker_clock import BrokerClock
from xau_edge.market_data.mt5.feed import Mt5Feed
from xau_edge.market_data.mt5.source import Mt5AccountError, load_mt5_module

DEFAULT_TERMINAL = r"C:\Program Files\FTMO Global Markets MT5 Terminal\terminal64.exe"
DEFAULT_CLOCK = "NY+7"


class TerminalUnavailableError(RuntimeError):
    """The terminal could not be started or is not logged in."""


@contextmanager
def open_feed(
    terminal_path: str | Path | None = None,
    *,
    broker_timezone: str = DEFAULT_CLOCK,
    client: Any | None = None,
    require_demo: bool = True,
    timeout_ms: int = 60_000,
) -> Iterator[Mt5Feed]:
    """Initialise the terminal with its own session (no credentials), yield a data-only feed.

    The terminal's already logged-in account is used; no login or password is passed or read. The
    DEMO guard runs before anything is read, and the terminal is shut down on exit.
    """
    module = client if client is not None else load_mt5_module()
    kwargs: dict[str, Any] = {"timeout": timeout_ms}
    if terminal_path is not None:
        kwargs["path"] = str(terminal_path)
    if not module.initialize(**kwargs):
        msg = f"MT5 initialize failed: {module.last_error()}"
        raise TerminalUnavailableError(msg)
    try:
        feed = Mt5Feed(module, BrokerClock.parse(broker_timezone), require_demo=require_demo)
        try:
            feed.guard()
        except Mt5AccountError:
            raise
        yield feed
    finally:
        module.shutdown()
