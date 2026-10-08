"""Paper trader: turns a validated signal into a paper order, through the risk engine and safety.

The order of checks is fixed: the signal must be BUY or SELL (never WAIT), unexpired and not already
traded; the risk engine sizes and may refuse; the safety limits may refuse; only then does the
paper broker fill. The signal's own entry zone, stop and target are used, never client input. The
same ``Signal`` schema that a future live executor would receive is journalled with every order.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from xau_edge.execution.interface import ClosedTrade, Order
from xau_edge.execution.paper import MarketBar, PaperExecutionBroker
from xau_edge.execution.safety import ExecutionSafety, day_key
from xau_edge.observability import log_event
from xau_edge.risk.engine import AccountState, MarketState, RiskEngine, TradeRequest
from xau_edge.signals.schema import Direction, Signal

_LOG = logging.getLogger(__name__)
_PRAGUE = ZoneInfo("Europe/Prague")


@dataclass(frozen=True)
class TradeOutcome:
    """Result of offering a signal to the trader."""

    accepted: bool
    reasons: tuple[str, ...]
    position_id: str | None = None
    lots: float = 0.0
    dry_run: bool = False


@dataclass
class _Day:
    key: str = ""
    start_balance: float = 0.0
    risk_taken: float = 0.0
    orders: int = 0
    consecutive_losses: int = 0


@dataclass
class PaperTrader:
    """Orchestrates signal -> risk -> safety -> paper broker, and tracks the daily statistics."""

    broker: PaperExecutionBroker
    risk: RiskEngine
    safety: ExecutionSafety = field(default_factory=ExecutionSafety)
    hold_bars: int = 20
    bar_minutes: int = 15
    _day: _Day = field(default_factory=_Day)
    _seen: set[str] = field(default_factory=set)
    _highest_eod: float = 0.0

    def __post_init__(self) -> None:
        self._highest_eod = self.broker.initial_capital

    def _roll_day(self, moment: datetime) -> None:
        key = day_key(moment.astimezone(_PRAGUE).date())
        if key != self._day.key:
            self._highest_eod = max(self._highest_eod, self.broker.balance)
            self._day = _Day(key=key, start_balance=self.broker.balance)

    def _account_state(self, moment: datetime) -> AccountState:
        info = self.broker.get_account()
        return AccountState(
            timestamp=moment,
            initial_capital=info.initial_capital,
            balance=info.balance,
            equity=info.equity,
            day_start_balance=self._day.start_balance,
            highest_eod_balance=self._highest_eod,
            open_positions=info.open_positions,
            open_lots=info.open_lots,
            risk_taken_today=self._day.risk_taken,
            consecutive_losses=self._day.consecutive_losses,
        )

    def on_bar(self, bar: MarketBar) -> list[ClosedTrade]:
        """Advance the simulated market and update daily statistics from closed trades."""
        self._roll_day(bar.time)
        closed = self.broker.update_market(bar)
        for trade in closed:
            self._day.consecutive_losses = (
                self._day.consecutive_losses + 1 if trade.net_pnl < 0 else 0
            )
        self.risk.check_account(self._account_state(bar.time))
        return closed

    def on_signal(  # noqa: PLR0911 - one early exit per refusal, in a fixed order
        self, signal: Signal, now: datetime, *, spread_points: float
    ) -> TradeOutcome:
        """Offer a signal; returns whether a paper order was (or, in dry-run, would be) placed."""
        if signal.direction is Direction.WAIT:
            return TradeOutcome(False, tuple(r.value for r in signal.reasons) or ("WAIT",))
        if signal.signal_expiry is not None and now > signal.signal_expiry:
            return TradeOutcome(False, ("SIGNAL_EXPIRED",))
        if signal.inputs_hash in self._seen:
            return TradeOutcome(False, ("DUPLICATE_SIGNAL",))
        if signal.entry_zone is None or signal.stop_loss is None or signal.take_profit_1 is None:
            return TradeOutcome(False, ("SIGNAL_INCOMPLETE",))

        self._roll_day(now)
        direction = 1 if signal.direction is Direction.BUY else -1
        mid = sum(signal.entry_zone) / 2
        decision = self.risk.evaluate(
            TradeRequest(
                timestamp=now, direction=direction, stop_distance=abs(mid - signal.stop_loss)
            ),
            self._account_state(now),
            MarketState(
                spread_points=spread_points, regime=signal.market_regime, news_blocked=False
            ),
        )
        if not decision.allowed:
            return TradeOutcome(False, decision.reasons)
        violations = self.safety.violations(
            symbol=signal.symbol, lots=decision.lots, orders_today=self._day.orders
        )
        if violations:
            return TradeOutcome(False, tuple(violations))
        if self.safety.dry_run:
            self._seen.add(signal.inputs_hash)
            log_event(_LOG, "paper.dry_run", signal_hash=signal.inputs_hash, lots=decision.lots)
            return TradeOutcome(True, (), None, decision.lots, dry_run=True)
        order = Order(
            order_id=signal.inputs_hash,
            symbol=signal.symbol,
            direction=direction,
            lots=decision.lots,
            stop_loss=signal.stop_loss,
            take_profit=signal.take_profit_1,
            signal_hash=signal.inputs_hash,
            max_hold_until=now + timedelta(minutes=self.bar_minutes * self.hold_bars),
        )
        try:
            position = self.broker.submit_order(order)
        except (ValueError, RuntimeError) as exc:
            log_event(_LOG, "paper.order_rejected", signal_hash=signal.inputs_hash, reason=str(exc))
            return TradeOutcome(False, ("ORDER_REJECTED",))
        self._seen.add(signal.inputs_hash)
        self._day.orders += 1
        self._day.risk_taken += decision.risk_amount
        return TradeOutcome(True, (), position.position_id, decision.lots)
