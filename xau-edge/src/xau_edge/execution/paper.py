"""Paper execution: simulated fills with the SAME rules as the backtest (ADR-0015, ADR-0018).

Bars are bid prices with a spread in points. Long entries pay the ask plus slippage, short entries
sell at the bid minus slippage; long exits trigger on bid prices, short exits on ask prices; a bar
touching both levels resolves to the stop; a stop that gaps fills at the open. Nothing here touches
a real account or any broker API.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from xau_edge.backtest.costs import CostModel
from xau_edge.execution.interface import AccountInfo, ClosedTrade, Order, Position
from xau_edge.observability import log_event

_LOG = logging.getLogger(__name__)
SYMBOL = "XAUUSD"


@dataclass(frozen=True)
class MarketBar:
    """One bid-price bar with its spread."""

    time: datetime
    open: float
    high: float
    low: float
    close: float
    spread_points: float


@dataclass(frozen=True)
class _Quote:
    time: datetime
    bid: float
    spread: float  # price units


class PaperExecutionBroker:
    """Simulated broker implementing ``ExecutionBroker``."""

    def __init__(
        self,
        initial_capital: float,
        *,
        costs: CostModel,
        journal_path: Path | str | None = None,
        mode: str = "forward",
    ) -> None:
        self.mode = mode
        self.initial_capital = initial_capital
        self.costs = costs
        self.balance = initial_capital
        self.closed: list[ClosedTrade] = []
        self._positions: dict[str, Position] = {}
        self._order_ids: set[str] = set()
        self._counter = 0
        self._quote: _Quote | None = None
        self._journal = Path(journal_path) if journal_path else None

    # ---- market data -------------------------------------------------------------------------

    def set_quote(self, time: datetime, *, bid: float, spread_points: float) -> None:
        """Set the current bid and spread (used for fills, floating equity and manual closes)."""
        self._quote = _Quote(time, bid, spread_points * self.costs.point)

    def update_market(self, bar: MarketBar) -> list[ClosedTrade]:
        """Process a new bar: triggers, time exits; returns the trades closed by it."""
        spread = bar.spread_points * self.costs.point
        slip = self.costs.slippage_points * self.costs.point
        closed: list[ClosedTrade] = []
        for position in list(self._positions.values()):
            d = position.direction
            if d > 0:
                stop_hit = bar.low <= position.stop_loss
                target_hit = bar.high >= position.take_profit
                gap = bar.open <= position.stop_loss
            else:
                stop_hit = bar.high + spread >= position.stop_loss
                target_hit = bar.low + spread <= position.take_profit
                gap = bar.open + spread >= position.stop_loss
            if stop_hit:
                if gap:
                    price = bar.open if d > 0 else bar.open + spread
                else:
                    price = position.stop_loss - slip if d > 0 else position.stop_loss + slip
                closed.append(self._close(position, bar.time, price, "STOP"))
            elif target_hit:
                closed.append(self._close(position, bar.time, position.take_profit, "TARGET"))
            elif position.max_hold_until is not None and bar.time >= position.max_hold_until:
                price = bar.close - slip if d > 0 else bar.close + spread + slip
                closed.append(self._close(position, bar.time, price, "TIME"))
        self._quote = _Quote(bar.time, bar.close, spread)
        return closed

    # ---- ExecutionBroker ---------------------------------------------------------------------

    def get_account(self) -> AccountInfo:
        """Balance, floating equity and exposure."""
        floating = sum(self._floating(p) for p in self._positions.values())
        return AccountInfo(
            initial_capital=self.initial_capital,
            balance=self.balance,
            equity=self.balance + floating,
            open_positions=len(self._positions),
            open_lots=sum(p.lots for p in self._positions.values()),
        )

    def get_positions(self) -> list[Position]:
        """Open positions, oldest first."""
        return list(self._positions.values())

    def submit_order(self, order: Order) -> Position:
        """Fill a market order at the current quote with spread and slippage."""
        if self._quote is None:
            msg = "no quote available: call set_quote or update_market first"
            raise RuntimeError(msg)
        if order.symbol != SYMBOL:
            msg = f"unsupported symbol {order.symbol!r}; only {SYMBOL}"
            raise ValueError(msg)
        if order.order_id in self._order_ids:
            msg = f"duplicate order id {order.order_id!r}"
            raise ValueError(msg)
        slip = self.costs.slippage_points * self.costs.point
        q = self._quote
        entry = q.bid + q.spread + slip if order.direction > 0 else q.bid - slip
        self._check_levels(order.direction, entry, order.stop_loss, order.take_profit)
        self._counter += 1
        position = Position(
            position_id=f"p{self._counter}",
            order_id=order.order_id,
            symbol=order.symbol,
            direction=order.direction,
            lots=order.lots,
            entry_price=entry,
            entry_time=q.time,
            stop_loss=order.stop_loss,
            take_profit=order.take_profit,
            signal_hash=order.signal_hash,
            max_hold_until=order.max_hold_until,
        )
        self._order_ids.add(order.order_id)
        self._positions[position.position_id] = position
        self._write(
            "order.filled",
            q.time,
            position.signal_hash,
            position_id=position.position_id,
            direction=position.direction,
            lots=position.lots,
            entry_price=entry,
            stop_loss=position.stop_loss,
            take_profit=position.take_profit,
        )
        return position

    def cancel_order(self, order_id: str) -> bool:
        """Orders fill immediately, so there is never a pending order to cancel."""
        return False

    def close_position(self, position_id: str, reason: str) -> ClosedTrade:
        """Close at the current quote (exit side, with slippage)."""
        position = self._positions[position_id]
        if self._quote is None:
            msg = "no quote available"
            raise RuntimeError(msg)
        slip = self.costs.slippage_points * self.costs.point
        q = self._quote
        price = q.bid - slip if position.direction > 0 else q.bid + q.spread + slip
        return self._close(position, q.time, price, reason)

    def modify_position(
        self,
        position_id: str,
        *,
        stop_loss: float | None = None,
        take_profit: float | None = None,
    ) -> Position:
        """Change protective levels; they must stay on the correct side of the current price."""
        position = self._positions[position_id]
        if self._quote is None:
            msg = "no quote available"
            raise RuntimeError(msg)
        q = self._quote
        ref = q.bid if position.direction > 0 else q.bid + q.spread  # exit side of the quote
        new_stop = position.stop_loss if stop_loss is None else stop_loss
        new_take = position.take_profit if take_profit is None else take_profit
        self._check_levels(position.direction, ref, new_stop, new_take)
        updated = position.model_copy(update={"stop_loss": new_stop, "take_profit": new_take})
        self._positions[position_id] = updated
        self._write(
            "position.modified",
            self._quote.time,
            updated.signal_hash,
            position_id=position_id,
            stop_loss=new_stop,
            take_profit=new_take,
        )
        return updated

    # ---- persistence (the trade desk survives an API restart) --------------------------------

    def export_state(self) -> dict[str, Any]:
        """Everything needed to rebuild this broker (JSON-safe)."""
        return {
            "balance": self.balance,
            "counter": self._counter,
            "order_ids": sorted(self._order_ids),
            "positions": [p.model_dump(mode="json") for p in self._positions.values()],
            "closed": [c.model_dump(mode="json") for c in self.closed],
            "quote": None
            if self._quote is None
            else {
                "time": self._quote.time.isoformat(),
                "bid": self._quote.bid,
                "spread": self._quote.spread,
            },
        }

    def import_state(self, state: dict[str, Any]) -> None:
        """Restore a state produced by :meth:`export_state` (replaces the current one)."""
        self.balance = float(state["balance"])
        self._counter = int(state["counter"])
        self._order_ids = set(state["order_ids"])
        self._positions = {p["position_id"]: Position.model_validate(p) for p in state["positions"]}
        self.closed = [ClosedTrade.model_validate(c) for c in state["closed"]]
        quote = state.get("quote")
        self._quote = (
            None
            if quote is None
            else _Quote(
                datetime.fromisoformat(quote["time"]), float(quote["bid"]), float(quote["spread"])
            )
        )

    # ---- internals ---------------------------------------------------------------------------

    @staticmethod
    def _check_levels(direction: int, ref: float, stop: float, take: float) -> None:
        if direction > 0:
            if not stop < ref:
                msg = "stop loss must be below the price for a long"
                raise ValueError(msg)
            if not take > ref:
                msg = "take profit must be above the price for a long"
                raise ValueError(msg)
        else:
            if not stop > ref:
                msg = "stop loss must be above the price for a short"
                raise ValueError(msg)
            if not take < ref:
                msg = "take profit must be below the price for a short"
                raise ValueError(msg)

    def _floating(self, position: Position) -> float:
        if self._quote is None:
            return 0.0
        q = self._quote
        mark = q.bid if position.direction > 0 else q.bid + q.spread
        move = (mark - position.entry_price) * position.direction
        return move * position.lots * self.costs.contract_size

    def _close(self, position: Position, time: datetime, price: float, reason: str) -> ClosedTrade:
        gross = (
            (price - position.entry_price)
            * position.direction
            * position.lots
            * self.costs.contract_size
        )
        commission = 2 * self.costs.commission_per_lot_per_side * position.lots
        nights = self.costs.rollover_nights(position.entry_time, time)
        swap = self.costs.swap_cost(position.direction, position.lots, nights)
        net = gross - commission + swap
        trade = ClosedTrade(
            position_id=position.position_id,
            direction=position.direction,
            lots=position.lots,
            entry_time=position.entry_time,
            exit_time=time,
            entry_price=position.entry_price,
            exit_price=price,
            reason=reason,
            gross_pnl=gross,
            commission=commission,
            swap=swap,
            net_pnl=net,
            risk_amount=abs(position.entry_price - position.stop_loss)
            * position.lots
            * self.costs.contract_size,
            signal_hash=position.signal_hash,
        )
        self.balance += net
        del self._positions[position.position_id]
        self.closed.append(trade)
        self._write(
            "position.closed",
            time,
            position.signal_hash,
            position_id=position.position_id,
            reason=reason,
            exit_price=price,
            net_pnl=net,
        )
        return trade

    def _write(self, event: str, time: datetime, signal_hash: str, **fields: Any) -> None:
        log_event(_LOG, f"paper.{event}", time=time, signal_hash=signal_hash, **fields)
        if self._journal is None:
            return
        self._journal.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "event": event,
            "mode": self.mode,
            "time": time.isoformat(),
            "signal_hash": signal_hash,
            **fields,
        }
        with self._journal.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, default=str, allow_nan=False) + "\n")
