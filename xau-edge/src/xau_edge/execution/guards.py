"""FTMO-driven guards (T2.12, T2.13): rollover, market close, request budget, auto-flatten.

Rules come from ``docs/research/ftmo-rules-from-source.md``. Every guard errs on the side of not
trading: a guard that cannot decide refuses.

* Midnight rollover: the daily-loss floor moves at 00:00 Europe/Prague, so a losing position held
  across it can breach on the new day. No new order whose planned holding crosses midnight inside
  the warning window.
* Market close: no new order close to the daily break or the weekend close (a forbidden practice
  per FTMO's page; confirm the margin with FTMO).
* Request budget: a hard cap on terminal requests per Prague day, counted in the persistent state
  (FTMO's page is paraphrased as "hyperactive bot, more than 2,000 requests a day").
* Auto-flatten: close the bot's positions and trip the kill switch when equity is within a set share
  of the initial capital of the daily-loss floor (or of the maximum-loss floor).
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import polars as pl

from xau_edge.execution.state import ExecutionState
from xau_edge.market_data.validators.market_calendar import MarketCalendar
from xau_edge.observability import log_event
from xau_edge.risk.engine import AccountState
from xau_edge.risk.prop_rules import PropProfile

_LOG = logging.getLogger(__name__)
PRAGUE = ZoneInfo("Europe/Prague")

MIDNIGHT_ROLLOVER_RISK = "MIDNIGHT_ROLLOVER_RISK"
NEAR_MARKET_CLOSE = "NEAR_MARKET_CLOSE"


def next_prague_midnight(now: datetime) -> datetime:
    """The next 00:00 Europe/Prague strictly after ``now`` (DST aware), in UTC."""
    local = now.astimezone(PRAGUE)
    midnight = datetime.combine(
        local.date() + timedelta(days=1), datetime.min.time(), tzinfo=PRAGUE
    )
    return midnight.astimezone(UTC)


def midnight_rollover_risk(
    now: datetime, hold_until: datetime, *, window_minutes: int = 120
) -> bool:
    """True if a position opened now could still be open at Prague midnight inside the window."""
    midnight = next_prague_midnight(now)
    in_window = (midnight - now) <= timedelta(minutes=window_minutes)
    return in_window and hold_until > midnight


def near_market_close(now: datetime, calendar: MarketCalendar, *, margin_minutes: int = 30) -> bool:
    """True if the market is closed now or closes within ``margin_minutes``."""
    moments = [now + timedelta(minutes=k) for k in range(margin_minutes + 1)]
    frame = pl.DataFrame({"t": moments}, schema={"t": pl.Datetime("us", "UTC")})
    closed = frame.select(calendar.closed_expr(pl.col("t")).alias("c"))["c"]
    return bool(closed.any())


@dataclass(frozen=True)
class EntryGuard:
    """Callable for the bridge: returns the reasons a new order must not open now."""

    calendar: MarketCalendar
    rollover_window_minutes: int = 120
    close_margin_minutes: int = 30

    def __call__(self, now: datetime, hold_until: datetime) -> list[str]:
        reasons: list[str] = []
        if midnight_rollover_risk(now, hold_until, window_minutes=self.rollover_window_minutes):
            reasons.append(MIDNIGHT_ROLLOVER_RISK)
        if near_market_close(now, self.calendar, margin_minutes=self.close_margin_minutes):
            reasons.append(NEAR_MARKET_CLOSE)
        return reasons


@dataclass(frozen=True)
class FlattenDecision:
    """Whether to flatten, and how far equity is from each floor (as a share of initial capital)."""

    flatten: bool
    daily_distance_pct: float
    max_distance_pct: float
    reason: str


def evaluate_flatten(
    account: AccountState, prop: PropProfile, *, distance_pct: float = 1.0
) -> FlattenDecision:
    """Flatten when equity is within ``distance_pct`` of initial capital from either floor."""
    daily_floor = prop.daily_loss_floor(
        account.initial_capital, day_start_balance=account.day_start_balance
    )
    max_floor = prop.max_loss_floor(
        account.initial_capital, highest_eod_balance=account.highest_eod_balance
    )
    daily = (account.equity - daily_floor) / account.initial_capital * 100.0
    maximum = (account.equity - max_floor) / account.initial_capital * 100.0
    if daily <= distance_pct:
        return FlattenDecision(True, daily, maximum, "AUTO_FLATTEN_DAILY_LOSS")
    if maximum <= distance_pct:
        return FlattenDecision(True, daily, maximum, "AUTO_FLATTEN_MAX_LOSS")
    return FlattenDecision(False, daily, maximum, "")


class RequestBudgetExceededError(RuntimeError):
    """The daily limit of terminal requests was reached; no further request is made today."""


class CountingMt5:
    """Counts every terminal call in the persistent state and refuses past the budget.

    ``last_error`` is not counted (it is a local read). Attributes that are not callable
    (constants) pass through. The proxy is an accounting device, not a security boundary.
    """

    def __init__(
        self,
        client: Any,
        state: ExecutionState,
        *,
        budget: int = 1000,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._inner = client
        self._state = state
        self._budget = budget
        self._clock = clock

    @property
    def budget(self) -> int:
        """The hard daily limit."""
        return self._budget

    def _day(self) -> str:
        return self._clock().astimezone(PRAGUE).date().isoformat()

    def used_today(self) -> int:
        """Requests counted for the current Prague day."""
        return self._state.requests_on(self._day())

    def __getattr__(self, name: str) -> Any:
        attribute = getattr(self._inner, name)
        if not callable(attribute) or name == "last_error":
            return attribute

        def counted(*args: Any, **kwargs: Any) -> Any:
            total = self._state.bump_requests(self._day())
            if total > self._budget:
                log_event(_LOG, "requests.budget_exceeded", logging.CRITICAL, used=total)
                msg = f"daily request budget {self._budget} exceeded"
                raise RequestBudgetExceededError(msg)
            return attribute(*args, **kwargs)

        return counted
