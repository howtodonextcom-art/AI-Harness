"""Run the collector forever: connect, collect, and on ANY failure report DISCONNECTED and retry.

A terminal that is not started yet, starts late, restarts, loses its broker connection, or a
transient read error must never end collection permanently. Each new session reconciles the
overlap window first, so bars closed while we were away are filled in (and logged), not lost.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from contextlib import AbstractContextManager
from datetime import UTC, datetime
from pathlib import Path

from xau_edge.market_data.collector import CollectorStatus, MarketCollector, write_status_file
from xau_edge.market_data.mt5.feed import Mt5Feed

LOG = logging.getLogger("xau_edge.collector")


def disconnected_status(reason: str, now: datetime | None = None) -> CollectorStatus:
    """The status written while there is no working session (never a credential)."""
    return CollectorStatus(
        updated_at=(now or datetime.now(UTC)).isoformat(),
        health="DISCONNECTED",
        reasons=[reason],
        market_status="UNKNOWN",
        connected=False,
        demo_account=False,
        server=None,
        broker_symbol="",
        quote=None,
        last_closed={},
        last_bar_age_seconds={},
        stored_rows={},
        stale_timeframes=[],
    )


def run_with_reconnect(
    connect: Callable[[], AbstractContextManager[Mt5Feed]],
    build: Callable[[Mt5Feed], MarketCollector],
    *,
    status_path: Path,
    stop: Callable[[], bool] = lambda: False,
    retry_seconds: float = 5.0,
    sleep: Callable[[float], None] = time.sleep,
    max_sessions: int | None = None,
    quote_interval: float = 1.0,
    bar_interval: float = 5.0,
) -> int:
    """Keep collecting until ``stop()``; returns how many sessions were opened."""
    sessions = 0
    while not stop() and (max_sessions is None or sessions < max_sessions):
        sessions += 1
        try:
            with connect() as feed:
                collector = build(feed)
                collector.reconcile_all(deep=True)
                LOG.info("collector session %s started", sessions)
                collector.run(
                    stop, quote_interval=quote_interval, bar_interval=bar_interval, sleep=sleep
                )
        except KeyboardInterrupt:
            raise
        except Exception as exc:
            reason = f"{type(exc).__name__}: {exc}"[:300]
            LOG.warning("collector session %s ended: %s", sessions, reason)
            write_status_file(status_path, disconnected_status(reason))
            sleep(retry_seconds)
    return sessions
