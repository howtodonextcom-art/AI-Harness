"""Paper trading rules (pure): fills, bar-by-bar stop/target management, PnL, swap, governor.

PAPER only: nothing here can place an order anywhere. Every assumption is explicit:

* entry fills at the executable quote (BUY at the ask, SELL at the bid) plus ``SLIPPAGE_POINTS``
  of adverse slippage (ASSUMED, the same figure the cost model uses);
* a position is managed on CLOSED M1 bars that open after the minute it was opened in (a bar that
  was already forming at the fill is never used: no look-back into prices before the entry);
* BUY exits at the bid (bar low/high), SELL exits at the ask (bar high/low + the bar's spread);
* when one bar reaches both the stop and the target the STOP wins (pessimistic, flagged
  ``ambiguous``); a stop fills with adverse slippage, a target fills exactly at its level;
* PnL uses the broker's ``tick_size``/``tick_value`` captured when the position opened; swap is
  ASSUMED from the terminal values read on 2026-10-08 (``core.costs``), one charge per 17:00 New
  York rollover held on a weekday; there is no commission (ASSUMED 0).

The governor (exposure, frequency, cooldown, daily loss) is V1's, with V1's thresholds: it refuses
NEW trades only; the daily-loss *flatten* floor is the only rule that closes a position.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Literal
from zoneinfo import ZoneInfo

from xau_edge_v2.core.costs import SLIPPAGE_POINTS, SWAP_LONG_POINTS, SWAP_SHORT_POINTS

Side = Literal["BUY", "SELL"]
ExitReason = Literal["STOP_LOSS", "TAKE_PROFIT", "MANUAL", "FLATTEN"]
_NEW_YORK = ZoneInfo("America/New_York")
_SATURDAY = 5
ROLLOVER_HOUR_NY = 17


@dataclass(frozen=True)
class Exit:
    price: float
    reason: ExitReason
    ambiguous: bool = False
    """The bar reached both levels; the stop was assumed first."""


def direction(side: Side) -> int:
    return 1 if side == "BUY" else -1


def entry_fill(side: Side, quote_entry: float, point: float) -> float:
    """The quote plus adverse slippage (a BUY pays more, a SELL receives less)."""
    return quote_entry + direction(side) * SLIPPAGE_POINTS * point


def evaluate_bar(
    side: Side,
    stop_loss: float,
    take_profit: float,
    *,
    high: float,
    low: float,
    spread_points: float,
    point: float,
) -> Exit | None:
    """Did this closed bar hit the stop or the target? (stop first when both)."""
    slip = SLIPPAGE_POINTS * point
    if side == "BUY":
        stop_hit, target_hit = low <= stop_loss, high >= take_profit
        stop_fill = stop_loss - slip
    else:
        ask = spread_points * point
        stop_hit, target_hit = high + ask >= stop_loss, low + ask <= take_profit
        stop_fill = stop_loss + slip
    if stop_hit:
        return Exit(stop_fill, "STOP_LOSS", ambiguous=target_hit)
    if target_hit:
        return Exit(take_profit, "TAKE_PROFIT")
    return None


def pnl_usd(
    side: Side, entry: float, exit_price: float, lots: float, tick_size: float, tick_value: float
) -> float:
    """Profit in account currency (before swap) for ``lots``."""
    return direction(side) * (exit_price - entry) / tick_size * tick_value * lots


def rollover_nights(opened: datetime, closed: datetime) -> int:
    """Daily 17:00 New York rollovers crossed (Monday to Friday only; triple swap not modelled)."""
    shift = timedelta(hours=ROLLOVER_HOUR_NY)
    a = opened.astimezone(_NEW_YORK).replace(tzinfo=None) - shift
    b = closed.astimezone(_NEW_YORK).replace(tzinfo=None) - shift
    days = max((b.date() - a.date()).days, 0)
    return sum(
        1 for d in range(1, days + 1) if (a.date() + timedelta(days=d)).weekday() < _SATURDAY
    )


def swap_usd(side: Side, lots: float, nights: int, point: float, contract_size: float) -> float:
    """ASSUMED swap (negative = cost) for ``nights`` rollovers."""
    points = SWAP_LONG_POINTS if side == "BUY" else SWAP_SHORT_POINTS
    return points * nights * lots * point * contract_size


def floating_pnl(
    side: Side,
    entry: float,
    bid: float,
    ask: float,
    lots: float,
    tick_size: float,
    tick_value: float,
) -> float:
    """Open profit at the current quote (a BUY would close at the bid, a SELL at the ask)."""
    mark = bid if side == "BUY" else ask
    return pnl_usd(side, entry, mark, lots, tick_size, tick_value)


def close_price_at_quote(side: Side, bid: float, ask: float) -> float:
    return bid if side == "BUY" else ask


# ---- governor ---------------------------------------------------------------------------------
@dataclass(frozen=True)
class GovernorConfig:
    """V1's thresholds, unchanged."""

    max_open_positions: int = 1
    max_total_risk_pct: float = 1.0
    max_trades_per_hour: int = 2
    max_trades_per_session: int = 3
    max_trades_per_day: int = 6
    cooldown_after_loss_minutes: int = 30
    cooldown_after_streak_minutes: int = 240
    loss_streak_limit: int = 3
    daily_loss_stop_pct: float = 2.0
    daily_loss_flatten_pct: float = 3.5


@dataclass(frozen=True)
class OpenRecord:
    opened_at: datetime
    session: str
    risk_pct: float
    closed: bool


@dataclass(frozen=True)
class CloseRecord:
    closed_at: datetime
    pnl: float


def daily_loss_pct(day_start_equity: float, equity: float) -> float:
    if day_start_equity <= 0:
        return 0.0
    return max(0.0, (day_start_equity - equity) / day_start_equity * 100.0)


def loss_streak(closes: list[CloseRecord]) -> int:
    streak = 0
    for c in reversed(closes):
        if c.pnl < 0:
            streak += 1
        else:
            break
    return streak


def cooldown_until(
    now: datetime, closes: list[CloseRecord], cfg: GovernorConfig
) -> datetime | None:
    """When the cooldown after the latest close ends (None when none is running)."""
    if not closes:
        return None
    last = closes[-1]
    ends: list[datetime] = []
    if loss_streak(closes) >= cfg.loss_streak_limit:
        ends.append(last.closed_at + timedelta(minutes=cfg.cooldown_after_streak_minutes))
    if last.pnl < 0:
        ends.append(last.closed_at + timedelta(minutes=cfg.cooldown_after_loss_minutes))
    live = [e for e in ends if e > now]
    return max(live) if live else None


def governor_check(
    cfg: GovernorConfig,
    now: datetime,
    session: str,
    new_risk_pct: float,
    *,
    opens: list[OpenRecord],
    opens_today: list[OpenRecord],
    closes: list[CloseRecord],
    day_start_equity: float,
    equity: float,
) -> list[str]:
    """Refusal codes for a NEW trade (empty: allowed). Codes match the decision's refusals.

    ``opens`` are all positions ever opened (the hourly rule looks back one hour), ``opens_today``
    those of the current broker day, ``closes`` every closed position in time order.
    """
    out: list[str] = []
    if daily_loss_pct(day_start_equity, equity) >= cfg.daily_loss_stop_pct:
        out.append("DAILY_LIMIT")
    if len(opens_today) >= cfg.max_trades_per_day:
        out.append("DAILY_LIMIT")
    if sum(1 for o in opens_today if o.session == session) >= cfg.max_trades_per_session:
        out.append("DAILY_LIMIT")
    if sum(1 for o in opens if now - o.opened_at < timedelta(hours=1)) >= cfg.max_trades_per_hour:
        out.append("DAILY_LIMIT")
    open_now = [o for o in opens if not o.closed]
    if len(open_now) >= cfg.max_open_positions:
        out.append("RISK_LIMIT")
    if sum(o.risk_pct for o in open_now) + new_risk_pct > cfg.max_total_risk_pct + 1e-9:
        out.append("RISK_LIMIT")
    if cooldown_until(now, closes, cfg) is not None:
        out.append("COOLDOWN")
    return list(dict.fromkeys(out))


def flatten_required(cfg: GovernorConfig, day_start_equity: float, equity: float) -> bool:
    return daily_loss_pct(day_start_equity, equity) >= cfg.daily_loss_flatten_pct
