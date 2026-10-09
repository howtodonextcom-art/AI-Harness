"""Safe diagnostics of the MT5 data path (environment, connection, history depth).

Pure functions over the read-only feed, so they run on a fake client in CI and on the real DEMO
terminal locally. Nothing here prints or returns a login, password, balance or token, and nothing
can send an order (the feed only reaches market-data functions).
"""

from __future__ import annotations

import importlib.metadata
import platform
import sys
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from xau_edge.domain.timeframe import Timeframe
from xau_edge.market_data.mt5.feed import (
    MAX_BARS_PER_CALL,
    Mt5Feed,
    SymbolMapping,
    SymbolNotFoundError,
)
from xau_edge.market_data.mt5.terminal import (
    TerminalCandidate,
    discover_terminals,
    select_terminal,
)

TICK_SEARCH_START = datetime(2010, 1, 1, tzinfo=UTC)
TICK_WINDOW = timedelta(minutes=10)


def package_info() -> dict[str, Any]:
    """Is the MetaTrader5 package installed, and which version."""
    try:
        return {"installed": True, "version": importlib.metadata.version("MetaTrader5")}
    except importlib.metadata.PackageNotFoundError:
        return {"installed": False, "version": None}


def environment_report(
    *, preferred: Path | None = None, candidates: list[TerminalCandidate] | None = None
) -> dict[str, Any]:
    """OS, Python, package and terminal candidates (no connection, no credentials)."""
    found = candidates if candidates is not None else discover_terminals()
    chosen = select_terminal(found, preferred=preferred)
    return {
        "os": platform.platform(),
        "windows": sys.platform == "win32",
        "python": platform.python_version(),
        "package": package_info(),
        "terminals_found": [c.as_dict() for c in found],
        "selected_terminal": None if chosen is None else str(chosen.path),
        "installation": "ALREADY_INSTALLED" if chosen is not None else "INSTALL_REQUIRED",
    }


def _earliest_with_data(
    has_data: Callable[[datetime], bool], lo: datetime, hi: datetime
) -> datetime | None:
    """Bisect for the first instant at which ``has_data`` turns true (data assumed contiguous)."""
    if not has_data(hi):
        return None
    if has_data(lo):
        return lo
    while hi - lo > timedelta(days=1):
        mid = lo + (hi - lo) / 2
        if has_data(mid):
            hi = mid
        else:
            lo = mid
    return hi


def earliest_tick(feed: Mt5Feed, symbol: str, now: datetime) -> datetime | None:
    """Earliest day with ticks (bisection over 10-minute windows around midday UTC)."""

    def has(moment: datetime) -> bool:
        day = moment.replace(hour=12, minute=0, second=0, microsecond=0)
        if day.weekday() >= 5:
            day -= timedelta(days=day.weekday() - 4)
        try:
            return bool(feed.ticks_range(symbol, day, day + TICK_WINDOW, limit=5))
        except RuntimeError:
            return False

    return _earliest_with_data(has, TICK_SEARCH_START, now - timedelta(days=2))


def volume_eras(frame: Any) -> list[dict[str, Any]]:
    """Contiguous year ranges with and without a non-zero ``real_volume`` (polars frame in).

    Empirical result for FTMO XAUUSD: a non-zero real volume exists only in an imported legacy
    era; its meaning is unverified, so tick volume remains the only volume used.
    """
    import polars as pl  # noqa: PLC0415

    by_year = (
        frame.with_columns(pl.col("timestamp").dt.year().alias("y"))
        .group_by("y")
        .agg(pl.len().alias("bars"), (pl.col("real_volume") != 0).sum().alias("nonzero"))
        .sort("y")
    )
    eras: list[dict[str, Any]] = []
    for row in by_year.iter_rows(named=True):
        kind = "REAL_VOLUME_PRESENT" if row["nonzero"] > 0 else "TICK_ONLY"
        if eras and eras[-1]["kind"] == kind:
            eras[-1]["to_year"] = row["y"]
            eras[-1]["bars"] += row["bars"]
            eras[-1]["nonzero_bars"] += row["nonzero"]
        else:
            eras.append(
                {"kind": kind, "from_year": row["y"], "to_year": row["y"],
                 "bars": row["bars"], "nonzero_bars": row["nonzero"]}
            )  # fmt: skip
    return eras


def bar_depth(
    feed: Mt5Feed, symbol: str, timeframe: Timeframe, max_bars: int | None
) -> dict[str, Any]:
    """How far back the terminal serves ``timeframe`` through ``copy_rates_from_pos``."""
    ceiling = min(MAX_BARS_PER_CALL, (max_bars - 1) if max_bars else MAX_BARS_PER_CALL)
    count = ceiling
    frame = None
    error = None
    while count >= 10:
        try:
            frame = feed.latest_bars(symbol, timeframe, count, include_forming=True)
            break
        except RuntimeError as exc:
            error = str(exc)
            count //= 2
    if frame is None or frame.height == 0:
        return {"available": False, "error": error, "requested": ceiling}
    return {
        "available": True,
        "count": frame.height,
        "requested": ceiling,
        "earliest": frame["timestamp"].min(),
        "latest": frame["timestamp"].max(),
        "limited_by_terminal_max_bars": bool(max_bars and frame.height >= min(count, max_bars - 1)),
        "tick_volume_positive": bool((frame["tick_volume"] > 0).all()),
        "real_volume_nonzero": bool((frame["real_volume"] != 0).any()),
        "volume_eras": volume_eras(frame),
    }


def connection_probe(
    feed: Mt5Feed,
    *,
    canonical: str = "XAUUSD",
    terminal_path: str | None = None,
    with_tick_depth: bool = True,
) -> dict[str, Any]:
    """The full structured answer to "can XAU EDGE read market data from this terminal"."""
    now = datetime.now(UTC)
    report: dict[str, Any] = {
        "terminal_found": terminal_path is not None,
        "terminal_path": terminal_path,
        "probed_at": now.isoformat(),
    }
    facts = feed.facts()
    report |= {
        "terminal_build": facts.build,
        "terminal_version": list(facts.version) if facts.version else None,
        "connected": facts.connected,
        "demo_account": facts.demo,
        "server": facts.server,
        "algo_trading_enabled": facts.trade_allowed,
        "terminal_max_bars": facts.max_bars,
    }
    if not facts.demo:
        report["error"] = "not a DEMO account: nothing else was read"
        return report
    try:
        mapping: SymbolMapping = feed.discover_symbol(canonical)
    except SymbolNotFoundError as exc:
        report["error"] = str(exc)
        return report
    selected = feed.select(mapping.broker_symbol)
    quote = feed.quote(mapping)
    report |= {
        "canonical_symbol": mapping.canonical_symbol,
        "broker_symbol": mapping.broker_symbol,
        "symbol_exact": mapping.exact,
        "symbol_selected": selected,
        "latest_tick_time": None if quote.timestamp is None else quote.timestamp.isoformat(),
        "latest_tick_age_seconds": quote.age_seconds,
        "bid_ask_available": quote.bid is not None and quote.ask is not None,
        "quote_note": quote.note,
    }
    depth: dict[str, Any] = {}
    for tf in (
        Timeframe.M1,
        Timeframe.M5,
        Timeframe.M15,
        Timeframe.M30,
        Timeframe.H1,
        Timeframe.H4,
    ):
        depth[tf.value] = bar_depth(feed, mapping.broker_symbol, tf, facts.max_bars)
        report[f"{tf.value}_available"] = depth[tf.value]["available"]
    report["bar_depth"] = depth
    report["rates_supported"] = any(d["available"] for d in depth.values())
    report["earliest_M1"] = depth["M1"].get("earliest")
    report["tick_volume_available"] = all(
        d.get("tick_volume_positive", False) for d in depth.values() if d["available"]
    )
    report["real_volume_available"] = any(
        d.get("real_volume_nonzero", False) for d in depth.values() if d["available"]
    )
    ticks_ok = False
    if with_tick_depth:
        first = earliest_tick(feed, mapping.broker_symbol, now)
        report["earliest_tick"] = None if first is None else first.isoformat()
        ticks_ok = first is not None
    else:
        try:
            ticks_ok = bool(feed.ticks_from(mapping.broker_symbol, now - timedelta(hours=2), 5))
        except RuntimeError:
            ticks_ok = False
    report["ticks_supported"] = ticks_ok
    return report
