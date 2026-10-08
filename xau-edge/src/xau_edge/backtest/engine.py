"""Event-driven backtest on M5 bars with spread, slippage, commission, swap and risk checks.

Model (documented in ADR-0015):

* Bars are BID prices; each bar has a spread in points, so ask = bid + spread.
* A signal decided at ``decision_time`` enters at the open of the first bar at or after it
  (``max_entry_gap`` guards against filling across a market closure).
* Long entry pays the ask plus slippage; short entry sells at the bid minus slippage. Stop and
  target
  distances are measured from the fill. Long exits trigger on bid prices, short exits on ask prices.
* A bar reaching both barriers resolves to the stop. A stop that gaps through its level fills at the
  open; other stop fills and time exits suffer adverse slippage; targets fill at their level.
* One position at a time; signals during a position are skipped and logged.
* Size, limits, the daily-loss buffer, spread and regime guards, news and the kill switch come from
  ``RiskEngine``. A prop-firm breach latches the kill switch for the rest of the run.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import numpy as np
import polars as pl
from pydantic import BaseModel, ConfigDict, Field

from xau_edge.backtest.costs import CostModel
from xau_edge.domain.timeframe import Timeframe
from xau_edge.news.calendar import EconomicCalendar, news_blocked
from xau_edge.observability import log_event
from xau_edge.risk.engine import AccountState, MarketState, RiskEngine, RiskLimits, TradeRequest
from xau_edge.risk.prop_rules import PropProfile

_LOG = logging.getLogger(__name__)
_PRAGUE = ZoneInfo("Europe/Prague")  # FTMO day boundary is midnight CE(S)T
_EXEC_MINUTES = 5
_REQUIRED_SIGNAL = ("decision_time", "direction", "atr", "stop_atr", "target_atr", "max_hold_bars")
_REQUIRED_BARS = ("timestamp", "open", "high", "low", "close", "spread")


class BacktestConfig(BaseModel):
    """Run settings."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    signal_timeframe: Timeframe = Timeframe.M15
    initial_capital: float = Field(default=100_000.0, gt=0)
    costs: CostModel = Field(default_factory=CostModel)
    limits: RiskLimits = Field(default_factory=RiskLimits)
    max_entry_gap_minutes: int = Field(default=30, ge=0)
    news_before_minutes: int = Field(default=15, ge=0)
    news_after_minutes: int = Field(default=15, ge=0)
    require_news_calendar: bool = True
    """Fail safe: refuse to run without a calendar; research runs must opt out explicitly."""


@dataclass(frozen=True)
class BacktestResult:
    """Trades, skipped signals (with reasons), the bar-level equity curve and the final state."""

    trades: pl.DataFrame
    skipped: pl.DataFrame
    equity: pl.DataFrame
    final_balance: float
    kill_switch_reason: str


def _prague_day(ts: datetime) -> date:
    return ts.astimezone(_PRAGUE).date()


def _validate(signals: pl.DataFrame, bars: pl.DataFrame) -> None:
    missing = [c for c in _REQUIRED_SIGNAL if c not in signals.columns]
    missing += [c for c in _REQUIRED_BARS if c not in bars.columns]
    if missing:
        msg = f"missing column(s): {', '.join(missing)}"
        raise ValueError(msg)
    if bars.height == 0 or not bars["timestamp"].is_sorted(descending=False):
        msg = "bars must be non-empty and sorted by timestamp"
        raise ValueError(msg)
    if signals.height and not signals["direction"].is_in([-1, 1]).all():
        msg = "direction must be -1 or 1 in every signal"
        raise ValueError(msg)
    ohlc = bars.select("open", "high", "low", "close", "spread")
    if not all(bool(ohlc[c].is_finite().all()) for c in ohlc.columns):
        msg = "bars must have finite open, high, low, close and spread"
        raise ValueError(msg)
    bad = bars.filter(
        (pl.col("high") < pl.col("low"))
        | (pl.col("open") > pl.col("high"))
        | (pl.col("open") < pl.col("low"))
        | (pl.col("close") > pl.col("high"))
        | (pl.col("close") < pl.col("low"))
        | (pl.col("spread") < 0)
    )
    if bad.height:
        msg = f"{bad.height} bar(s) have inconsistent OHLC or a negative spread"
        raise ValueError(msg)
    if bars["timestamp"].is_duplicated().any():
        msg = "bars contain duplicate timestamps"
        raise ValueError(msg)


@dataclass
class _Account:
    balance: float
    day: date
    day_start: float
    highest_eod: float
    risk_today: float = 0.0
    consecutive_losses: int = 0

    def roll_to(self, day: date) -> None:
        if day != self.day:
            self.highest_eod = max(self.highest_eod, self.balance)
            self.day_start = self.balance
            self.risk_today = 0.0
            self.consecutive_losses = 0
            self.day = day


def run_backtest(  # noqa: PLR0912, PLR0915 - one sequential simulation loop
    signals: pl.DataFrame,
    bars: pl.DataFrame,
    config: BacktestConfig,
    prop: PropProfile,
    *,
    calendar: EconomicCalendar | None = None,
) -> BacktestResult:
    """Simulate ``signals`` on M5 ``bars`` (columns: timestamp, open, high, low, close, spread)."""
    _validate(signals, bars)
    costs, limits = config.costs, config.limits
    if calendar is None and config.require_news_calendar:
        msg = "a news calendar is required (set require_news_calendar=False for research runs)"
        raise ValueError(msg)
    if limits.require_regime and signals.height and "regime" not in signals.columns:
        msg = "signals need a regime column (or set limits.require_regime=False)"
        raise ValueError(msg)
    engine = RiskEngine(limits, prop)
    ts_arr = bars["timestamp"].to_numpy()
    ts_list: list[datetime] = bars["timestamp"].to_list()
    o, h, lo, c = (bars[k].to_numpy() for k in ("open", "high", "low", "close"))
    spr = bars["spread"].to_numpy() * costs.point
    n = bars.height
    slip = costs.slippage_points * costs.point
    per_lot = costs.contract_size

    acct = _Account(
        config.initial_capital,
        _prague_day(ts_list[0]),
        config.initial_capital,
        config.initial_capital,
    )
    trades: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    equity = np.empty(n)
    equity_low = np.empty(n)
    cursor = 0
    last_exit = -1
    has_regime = "regime" in signals.columns
    ordered = signals.sort("decision_time")

    def skip(row: dict[str, Any], reason: str) -> None:
        skipped.append(
            {"decision_time": row["decision_time"], "direction": row["direction"], "reason": reason}
        )

    for row in ordered.iter_rows(named=True):
        dt: datetime = row["decision_time"]
        if dt.tzinfo is None:
            msg = "decision_time must be timezone-aware"
            raise ValueError(msg)
        utc_naive = np.datetime64(dt.astimezone(UTC).replace(tzinfo=None))
        i = int(np.searchsorted(ts_arr, utc_naive, side="left"))
        if i >= n:
            skip(row, "NO_BAR")
            continue
        entry_time = ts_list[i]
        if entry_time - dt > timedelta(minutes=config.max_entry_gap_minutes):
            skip(row, "ENTRY_GAP")
            continue
        if i <= last_exit:
            skip(row, "IN_POSITION")
            continue
        atr = float(row["atr"])
        if not np.isfinite(atr) or atr <= 0:
            skip(row, "BAD_ATR")
            continue

        acct.roll_to(_prague_day(entry_time))
        account = AccountState(
            timestamp=entry_time,
            initial_capital=config.initial_capital,
            balance=acct.balance,
            equity=acct.balance,
            day_start_balance=acct.day_start,
            highest_eod_balance=acct.highest_eod,
            open_positions=0,
            open_lots=0.0,
            risk_taken_today=acct.risk_today,
            consecutive_losses=acct.consecutive_losses,
        )
        engine.check_account(account)
        blocked = False
        if calendar is not None:
            blocked = news_blocked(
                calendar,
                entry_time,
                before_minutes=config.news_before_minutes,
                after_minutes=config.news_after_minutes,
            )
        direction = int(row["direction"])
        stop_dist = float(row["stop_atr"]) * atr
        regime = row["regime"] if has_regime else None
        decision = engine.evaluate(
            TradeRequest(timestamp=entry_time, direction=direction, stop_distance=stop_dist),
            account,
            MarketState(
                spread_points=float(spr[i] / costs.point), regime=regime, news_blocked=blocked
            ),
        )
        if not decision.allowed:
            skip(row, "+".join(decision.reasons))
            continue

        lots = decision.lots
        acct.risk_today += decision.risk_amount  # credited to the day the trade is taken
        entry = o[i] + spr[i] + slip if direction > 0 else o[i] - slip
        stop = entry - direction * stop_dist
        target = entry + direction * float(row["target_atr"]) * atr
        hold_bars = max(
            1, int(row["max_hold_bars"] * config.signal_timeframe.minutes) // _EXEC_MINUTES
        )
        last_bar = min(i + hold_bars - 1, n - 1)

        exit_idx, exit_reason, exit_price, slipped = last_bar, "TIME", 0.0, 1
        mfe = mae = 0.0
        for k in range(i, last_bar + 1):
            if direction > 0:
                stop_hit = lo[k] <= stop
                target_hit = h[k] >= target
                gap = k > i and o[k] <= stop
                mfe = max(mfe, h[k] - entry)
                mae = max(mae, entry - lo[k])
            else:
                stop_hit = h[k] + spr[k] >= stop
                target_hit = lo[k] + spr[k] <= target
                gap = k > i and o[k] + spr[k] >= stop
                mfe = max(mfe, entry - (lo[k] + spr[k]))
                mae = max(mae, h[k] + spr[k] - entry)
            if stop_hit:
                exit_idx, exit_reason = k, "STOP"
                if gap:
                    exit_price = o[k] if direction > 0 else o[k] + spr[k]
                else:
                    exit_price = stop - slip if direction > 0 else stop + slip
                    slipped += 1
                break
            if target_hit:
                exit_idx, exit_reason, exit_price = k, "TARGET", target
                break
        else:
            exit_idx = last_bar
            if last_bar < i + hold_bars - 1:
                exit_reason = "DATA_END"
            exit_price = c[exit_idx] - slip if direction > 0 else c[exit_idx] + spr[exit_idx] + slip
            slipped += 1

        exit_time = ts_list[exit_idx]
        gross = (exit_price - entry) * direction * lots * per_lot
        commission = 2 * costs.commission_per_lot_per_side * lots
        nights = costs.rollover_nights(entry_time, exit_time)
        swap = costs.swap_cost(direction, lots, nights)
        net = gross - commission + swap
        spread_cost = (spr[i] if direction > 0 else spr[exit_idx]) * lots * per_lot
        slippage_cost = slipped * slip * lots * per_lot
        # equity path: flat, then floating during the trade, then the new balance at the exit bar
        equity[cursor:i] = acct.balance
        equity_low[cursor:i] = acct.balance
        before = acct.balance
        trade_low = before
        for k in range(i, exit_idx + 1):
            worst = (lo[k] - entry) if direction > 0 else (entry - (h[k] + spr[k]))
            worst_equity = before + worst * lots * per_lot
            trade_low = min(trade_low, worst_equity)
            equity_low[k] = worst_equity
            if k < exit_idx:
                mark = c[k] if direction > 0 else c[k] + spr[k]
                equity[k] = before + (mark - entry) * direction * lots * per_lot
        acct.roll_to(_prague_day(exit_time))
        acct.balance += net
        equity[exit_idx] = acct.balance
        equity_low[exit_idx] = min(equity_low[exit_idx], acct.balance)
        trade_low = min(trade_low, acct.balance)
        cursor = exit_idx + 1
        last_exit = exit_idx
        acct.consecutive_losses = acct.consecutive_losses + 1 if net < 0 else 0

        trades.append(
            {
                "signal_time": dt,
                "entry_time": entry_time,
                "exit_time": exit_time,
                "direction": direction,
                "lots": lots,
                "entry_price": entry,
                "exit_price": float(exit_price),
                "exit_reason": exit_reason,
                "stop_price": stop,
                "target_price": target,
                "risk_amount": decision.risk_amount,
                "gross_pnl": gross,
                "spread_cost": spread_cost,
                "slippage_cost": slippage_cost,
                "commission": commission,
                "swap": swap,
                "net_pnl": net,
                "net_r": net / decision.risk_amount,
                "mfe_r": mfe / stop_dist,
                "mae_r": mae / stop_dist,
                "balance_after": acct.balance,
                "strategy": row.get("strategy", ""),
            }
        )
        engine.check_account(
            AccountState(
                timestamp=exit_time,
                initial_capital=config.initial_capital,
                balance=acct.balance,
                equity=min(trade_low, acct.balance),
                day_start_balance=acct.day_start,
                highest_eod_balance=acct.highest_eod,
                open_positions=0,
                open_lots=0.0,
                risk_taken_today=acct.risk_today,
                consecutive_losses=acct.consecutive_losses,
            )
        )

    equity[cursor:] = acct.balance
    equity_low[cursor:] = acct.balance
    log_event(
        _LOG,
        "backtest.done",
        trades=len(trades),
        skipped=len(skipped),
        final_balance=acct.balance,
        kill_switch=engine.kill_switch.reason,
    )
    return BacktestResult(
        trades=_frame(trades, _TRADE_SCHEMA),
        skipped=_frame(skipped, _SKIP_SCHEMA),
        equity=pl.DataFrame(
            {"timestamp": bars["timestamp"], "equity": equity, "equity_low": equity_low}
        ),
        final_balance=acct.balance,
        kill_switch_reason=engine.kill_switch.reason,
    )


_UTC = pl.Datetime("us", "UTC")
_TRADE_SCHEMA: dict[str, pl.DataType | type[pl.DataType]] = {
    "signal_time": _UTC,
    "entry_time": _UTC,
    "exit_time": _UTC,
    "direction": pl.Int8,
    "lots": pl.Float64,
    "entry_price": pl.Float64,
    "exit_price": pl.Float64,
    "exit_reason": pl.String,
    "stop_price": pl.Float64,
    "target_price": pl.Float64,
    "risk_amount": pl.Float64,
    "gross_pnl": pl.Float64,
    "spread_cost": pl.Float64,
    "slippage_cost": pl.Float64,
    "commission": pl.Float64,
    "swap": pl.Float64,
    "net_pnl": pl.Float64,
    "net_r": pl.Float64,
    "mfe_r": pl.Float64,
    "mae_r": pl.Float64,
    "balance_after": pl.Float64,
    "strategy": pl.String,
}
_SKIP_SCHEMA: dict[str, pl.DataType | type[pl.DataType]] = {
    "decision_time": _UTC,
    "direction": pl.Int8,
    "reason": pl.String,
}


def _frame(
    rows: list[dict[str, Any]], schema: dict[str, pl.DataType | type[pl.DataType]]
) -> pl.DataFrame:
    return pl.DataFrame(rows, schema=schema)


def prop_breaches(
    equity: pl.DataFrame, prop: PropProfile, *, initial_capital: float
) -> dict[str, Any]:
    """Days on which equity fell below the daily floor, and whether the max-loss floor was hit.

    Day start balance is approximated by the last equity value of the previous day (exact when the
    account is flat at midnight, which the baselines almost always are).
    """
    frame = equity.with_columns(
        pl.col("timestamp").dt.convert_time_zone("Europe/Prague").dt.date().alias("day")
    )
    low_col = "equity_low" if "equity_low" in frame.columns else "equity"
    days = frame.group_by("day", maintain_order=True).agg(
        pl.col(low_col).min().alias("low"), pl.col("equity").last().alias("close")
    )
    breached: list[date] = []
    prev_close = initial_capital
    highest_eod = initial_capital
    max_hit = False
    for day, low, close in days.iter_rows():
        floor = prop.daily_loss_floor(initial_capital, day_start_balance=prev_close)
        if low < floor:
            breached.append(day)
        if low < prop.max_loss_floor(initial_capital, highest_eod_balance=highest_eod):
            max_hit = True
        prev_close = close
        highest_eod = max(highest_eod, close)
    return {"daily": breached, "max_loss": max_hit}
