"""Everything the routes share: settings, read-only stores, live feed, calendar."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from xau_edge_v2.config import Settings
from xau_edge_v2.core.market_state import SnapshotMemo
from xau_edge_v2.data.bar_store import BarStore, Coverage
from xau_edge_v2.data.live_feed import LiveFeed
from xau_edge_v2.data.tick_store import TickStore
from xau_edge_v2.domain.market import BrokerClock, MarketCalendar
from xau_edge_v2.paper.desk import PaperDesk


@dataclass(frozen=True)
class AppContext:
    settings: Settings
    store: BarStore
    ticks: TickStore
    live: LiveFeed
    calendar: MarketCalendar
    started: datetime
    broker_clock: BrokerClock
    desk: PaperDesk
    memo: SnapshotMemo = field(default_factory=SnapshotMemo)
    cache: dict[str, object] = field(default_factory=dict)
    """Live decision cache (about a second): the page, the socket and the engine share one run."""

    def data_version(self, cov: Coverage) -> str:
        """Changes whenever the newest stored bar or the file count changes."""
        newest = "none" if cov.newest is None else cov.newest.strftime("%Y%m%dT%H%M%S")
        return f"{newest}-{cov.files}"
