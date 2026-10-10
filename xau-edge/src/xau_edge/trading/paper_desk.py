"""The paper trading desk: the existing ``PaperExecutionBroker`` driven by Trading Core decisions.

No second paper engine: fills, stops, targets, time exits, costs and the journal are the broker's.
The desk adds what the broker lacks for a daily tool:

* the lifecycle PENDING -> OPEN -> CLOSED, or PENDING -> CANCELLED (a fill that cannot happen);
* idempotence: one order per setup (``setup_id``); a duplicate or a double close is refused;
* automatic exits on every new CLOSED M1 bar: stop, target, time, and (when enabled) invalidation,
  with break-even / trailing from the position manager (both OFF by default);
* a complete journal (decision snapshot, market state, risk, lot, costs, exit reason, R, MFE, MAE,
  duration, strategy version, code SHA) and state that survives a restart.

Everything is simulated: nothing here can reach MT5, an account or a real order.
"""

from __future__ import annotations

import json
import logging
import math
import os
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from pathlib import Path
from typing import Any, Protocol

import polars as pl

from xau_edge.backtest.costs import CostModel
from xau_edge.execution.interface import ClosedTrade, Order
from xau_edge.execution.paper import MarketBar, PaperExecutionBroker
from xau_edge.market_data.atomic import atomic_write_text
from xau_edge.trading.governor import GovernorConfig, TradeGovernor
from xau_edge.trading.paper_recovery import diff_against_state, replay_journal
from xau_edge.trading.position_manager import (
    ManagerConfig,
    ManagerContext,
    PositionState,
    SlStage,
    apply,
    evaluate,
)
from xau_edge.trading.risk_calc import MAX_RISK_PCT, RISK_CHOICES
from xau_edge.trading.schema import TradeDecision, TradingSignal
from xau_edge.trading.sizing import SymbolSpec, size_for_risk

_LOG = logging.getLogger(__name__)
NO_TIME_EXIT = 10**7
"""The manager's own time exit is parked: ``max_hold_until`` is the single time exit."""


class QuoteLike(Protocol):
    """The executable quote the desk needs (``live_source.QuoteView`` satisfies it)."""

    @property
    def bid(self) -> float: ...

    @property
    def ask(self) -> float: ...

    @property
    def spread_points(self) -> float: ...

    @property
    def stale(self) -> bool: ...


@dataclass(frozen=True)
class BarExtras:
    """Market facts the position manager needs besides the bar itself."""

    atr: float | None = None
    swing_low: float | None = None
    swing_high: float | None = None
    invalidated: bool = False


class PaperStatus(StrEnum):
    PENDING = "PENDING"
    OPEN = "OPEN"
    CLOSED = "CLOSED"
    CANCELLED = "CANCELLED"


class DeskExit(StrEnum):
    STOP_LOSS = "STOP_LOSS"
    TAKE_PROFIT = "TAKE_PROFIT"
    TIME_EXIT = "TIME_EXIT"
    INVALIDATED = "INVALIDATED"
    MANUAL_CLOSE = "MANUAL_CLOSE"
    CLOSURE_CLOSE = "CLOSURE_CLOSE"


class ClosurePolicy(StrEnum):
    """What the PAPER desk does about a market closure (weekend, daily break, holiday).

    This is position management for the simulated account only; it never changes a decision.
    """

    BLOCK_NEW_NEAR_CLOSE = "BLOCK_NEW_NEAR_CLOSE"
    """Safe default: no new entry when the maximum hold could run into a closure."""
    CLOSE_BEFORE_CLOSURE = "CLOSE_BEFORE_CLOSURE"
    """Entries allowed; an open trade is closed shortly before the closure."""
    HOLD_ACROSS_CLOSE = "HOLD_ACROSS_CLOSE"
    """Entries allowed; the trade is held across the closure (exits at the first bar after)."""


STATE_ERROR = "PAPER_STATE_ERROR"
WRITER_ERROR = "WRITER_LOCK"
CLOSURE_NEAR = "CLOSURE_NEAR"


_BROKER_REASON = {
    "STOP": DeskExit.STOP_LOSS.value,
    "TARGET": DeskExit.TAKE_PROFIT.value,
    "TIME": DeskExit.TIME_EXIT.value,
}


class DeskRefusal(Exception):  # noqa: N818 - a refusal is a normal outcome, not an error
    """The desk refuses a request, with a stable machine code (HTTP 409 at the API)."""

    def __init__(self, code: str, message: str = "") -> None:
        super().__init__(f"{code}: {message}" if message else code)
        self.code = code
        self.message = message or code


@dataclass(frozen=True)
class DeskConfig:
    capital: float = 10_000.0
    """Simulated account size (a paper number: the real FTMO balance is never read or shown)."""
    allowed_risk: tuple[float, ...] = RISK_CHOICES
    max_hold_minutes: int = 120
    max_entry_drift_r: float = 0.25
    """A fill further than this share of the stop distance from the plan is cancelled."""
    manager: ManagerConfig = field(
        default_factory=lambda: ManagerConfig(
            close_on_invalidation=False, max_hold_minutes=NO_TIME_EXIT
        )
    )
    governor: GovernorConfig = field(default_factory=GovernorConfig)
    closure_policy: ClosurePolicy = ClosurePolicy.BLOCK_NEW_NEAR_CLOSE
    closure_buffer_minutes: int = 5
    """Used by CLOSE_BEFORE_CLOSURE: close when a closure starts within this many minutes."""


def _iso(value: datetime | None) -> str | None:
    return None if value is None else value.astimezone(UTC).isoformat()


def _parse(value: str | None) -> datetime | None:
    return None if value is None else datetime.fromisoformat(value)


class PaperDesk:
    """One simulated account, one trade at a time, every action journalled."""

    def __init__(
        self,
        root: Path | str,
        config: DeskConfig | None = None,
        *,
        costs: CostModel | None = None,
        code_version: str = "unknown",
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
        writable: bool = True,
        source_mode: str = "LIVE",
    ) -> None:
        self.writable = writable
        """False when another process owns the directory: the desk then only reads."""
        self.source_mode = source_mode
        self.closure_probe: Callable[[datetime, int], tuple[datetime, str] | None] | None = None
        """``(now, horizon_minutes) -> (closure start, kind)`` or None; set by the engine."""
        self.root = Path(root)
        self.config = config or DeskConfig()
        self.code_version = code_version
        self._clock = clock
        self.broker = PaperExecutionBroker(
            self.config.capital,
            costs=costs or CostModel(),
            journal_path=self.root / "paper_broker.jsonl",
            mode="trade-desk",
        )
        self.trades: dict[str, dict[str, Any]] = {}
        self.governor = TradeGovernor(self.config.governor)
        self.last_bar: datetime | None = None
        self.load_error: str | None = None
        self.integrity_error: str | None = None
        self.recovered_orphans: list[str] = []
        self._load()
        self._reconcile()

    # ---- persistence -------------------------------------------------------------------------

    @property
    def _state_path(self) -> Path:
        return self.root / "paper_desk.json"

    @property
    def _journal_path(self) -> Path:
        return self.root / "paper_journal.jsonl"

    def _save(self) -> None:
        if not self.writable:
            raise DeskRefusal(WRITER_ERROR, "another process owns the paper desk")
        payload = {
            "version": 1,
            "saved_at": _iso(self._clock()),
            "last_bar": _iso(self.last_bar),
            "broker": self.broker.export_state(),
            "trades": self.trades,
        }
        atomic_write_text(self._state_path, json.dumps(payload, default=str))

    def _set_aside(self, why: str) -> None:
        """Keep an unreadable state file for forensics and say so (never silently start empty)."""
        stamp = f"{self._clock():%Y%m%dT%H%M%S}"
        aside = self._state_path.with_name(f"{self._state_path.name}.corrupt-{stamp}")
        try:
            self._state_path.replace(aside)
        except OSError:
            aside = self._state_path
        self.load_error = (
            f"paper desk state was unreadable ({why}); it was set aside as {aside.name} and the "
            "desk started EMPTY: earlier paper trades are only in paper_journal.jsonl"
        )
        _LOG.error(self.load_error)

    def _load(self) -> None:
        if not self._state_path.exists():
            return
        try:
            raw = json.loads(self._state_path.read_text(encoding="utf-8"))
        except OSError:
            return
        except ValueError as exc:
            self._set_aside(type(exc).__name__)
            return
        try:
            self.broker.import_state(raw["broker"])
            self.trades = dict(raw["trades"])
            self.last_bar = _parse(raw.get("last_bar"))
        except (KeyError, TypeError, ValueError) as exc:
            self._set_aside(type(exc).__name__)
            self.trades = {}
            self.last_bar = None
            return
        for rec in self.trades.values():  # rebuild the governor's memory
            if rec["status"] in (PaperStatus.OPEN, PaperStatus.CLOSED):
                self.governor.record_open(
                    rec["trade_id"],
                    _parse(rec["opened_at"]) or self._clock(),
                    rec.get("session", "?"),
                    rec["risk_pct"],
                )
            if rec["status"] == PaperStatus.CLOSED:
                self.governor.record_close(
                    rec["trade_id"],
                    _parse(rec["closed_at"]) or self._clock(),
                    float(rec["net_pnl"]),
                )

    def _journal(self, event: str, record: dict[str, Any]) -> None:
        """Append a line and fsync it: the journal is the commit log (see paper_recovery)."""
        if not self.writable:
            raise DeskRefusal(WRITER_ERROR, "another process owns the paper desk")
        self.root.mkdir(parents=True, exist_ok=True)
        line = json.dumps(
            {"event": event, "at": _iso(self._clock()), **record}, default=str, sort_keys=True
        )
        with self._journal_path.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")
            handle.flush()
            os.fsync(handle.fileno())

    # ---- integrity ---------------------------------------------------------------------------

    @property
    def fault(self) -> tuple[str, str] | None:
        """(code, message) when the desk must not take or change anything, else None."""
        if not self.writable:
            return WRITER_ERROR, "another process owns the paper desk (single writer)"
        if self.load_error:
            return STATE_ERROR, self.load_error
        if self.integrity_error:
            return STATE_ERROR, self.integrity_error
        return None

    def _reconcile(self) -> None:
        """Compare snapshot and journal; close crashed intents; fail closed on a mismatch."""
        if self.load_error:
            return
        replay = replay_journal(self._journal_path)
        state_exists = self._state_path.exists()
        if not replay.events and not state_exists:
            return
        state: dict[str, Any] | None = None
        if state_exists:
            try:
                state = json.loads(self._state_path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                return  # _load already reported it
        differences = diff_against_state(replay, state, initial_capital=self.config.capital)
        if replay.orphans and self.writable and not differences:
            for tid in replay.orphans:  # crash before the fill committed: nothing exists to recover
                record = replay.trades[tid]
                self._journal(
                    "paper.abort",
                    {
                        "trade_id": tid,
                        "setup_id": record.get("setup_id"),
                        "why": "CRASH_BEFORE_COMMIT",
                    },
                )
                record.update(
                    status=PaperStatus.CANCELLED.value, cancel_reason="CRASH_BEFORE_COMMIT"
                )
                self.trades[tid] = record
            self.recovered_orphans = list(replay.orphans)
            self._save()
        if differences:
            shown = "; ".join(differences[:3]) + (" ..." if len(differences) > 3 else "")
            self.integrity_error = (
                "the paper state and its journal disagree (" + shown + "). New paper entries are "
                "blocked: run scripts/paper_recover.py (dry-run), then --apply"
            )
            _LOG.error(self.integrity_error)

    # ---- reading -----------------------------------------------------------------------------

    def open_trade(self) -> dict[str, Any] | None:
        for rec in self.trades.values():
            if rec["status"] == PaperStatus.OPEN:
                return rec
        return None

    def closed_trades(self) -> list[dict[str, Any]]:
        done = [
            r
            for r in self.trades.values()
            if r["status"] in (PaperStatus.CLOSED, PaperStatus.CANCELLED)
        ]
        return sorted(
            done, key=lambda r: r.get("closed_at") or r.get("created_at") or "", reverse=True
        )

    def equity(self, quote: QuoteLike | None, now: datetime) -> float:
        if quote is not None:
            self.broker.set_quote(now, bid=quote.bid, spread_points=quote.spread_points)
        return self.broker.get_account().equity

    def account(self, quote: QuoteLike | None, now: datetime) -> dict[str, Any]:
        equity = self.equity(quote, now)
        acct = self.broker.get_account()
        return {
            "simulated": True,
            "initial_capital": acct.initial_capital,
            "balance": round(acct.balance, 2),
            "equity": round(equity, 2),
            "open_positions": acct.open_positions,
            "open_lots": acct.open_lots,
        }

    def day_start_equity(self, now: datetime) -> float:
        today = now.astimezone(UTC).date()
        pnl_today = sum(
            float(r["net_pnl"])
            for r in self.trades.values()
            if r["status"] == PaperStatus.CLOSED
            and (_parse(r["closed_at"]) or now).astimezone(UTC).date() == today
        )
        return self.broker.balance - pnl_today

    def can_open(
        self, now: datetime, session: str, risk_pct: float, quote: QuoteLike | None
    ) -> list[str]:
        """Why a NEW paper trade is refused right now (empty: allowed): desk faults, a closure that
        the maximum hold could run into, then the governor's reasons."""
        out: list[str] = []
        if self.fault is not None:
            out.append(self.fault[0])
        if self.closure_blocks(now):
            out.append(CLOSURE_NEAR)
        equity = self.equity(quote, now)
        out.extend(
            r.value
            for r in self.governor.check(
                now, session, risk_pct, day_start_equity=self.day_start_equity(now), equity=equity
            )
        )
        return out

    def closure_blocks(self, now: datetime) -> tuple[datetime, str] | None:
        """(closure start, kind) when the policy refuses an entry now, else None."""
        policy = self.config.closure_policy
        if self.closure_probe is None or policy is ClosurePolicy.HOLD_ACROSS_CLOSE:
            return None
        horizon = (
            self.config.max_hold_minutes
            if policy is ClosurePolicy.BLOCK_NEW_NEAR_CLOSE
            else self.config.closure_buffer_minutes
        )
        return self.closure_probe(now, horizon)

    def closure_due(self, now: datetime) -> bool:
        """CLOSE_BEFORE_CLOSURE: a closure starts within the buffer."""
        if (
            self.config.closure_policy is not ClosurePolicy.CLOSE_BEFORE_CLOSURE
            or not self.closure_probe
        ):
            return False
        return self.closure_probe(now, self.config.closure_buffer_minutes) is not None

    def position_view(self, quote: QuoteLike | None, now: datetime) -> dict[str, Any] | None:
        rec = self.open_trade()
        if rec is None:
            return None
        view = dict(rec)
        side = 1 if rec["side"] == "BUY" else -1
        view["duration_minutes"] = round(
            (now - (_parse(rec["opened_at"]) or now)).total_seconds() / 60, 1
        )
        if quote is not None:
            mark = quote.bid if side > 0 else quote.ask  # the side a close would use
            risk = abs(rec["fill_price"] - rec["initial_sl"])
            move = (mark - rec["fill_price"]) * side
            view["current_price"] = mark
            view["unrealized_pnl"] = round(move * rec["lots"] * self.broker.costs.contract_size, 2)
            view["unrealized_r"] = round(move / risk, 3) if risk > 0 else None
        return view

    # ---- open --------------------------------------------------------------------------------

    def open_from_decision(
        self,
        decision: TradingSignal,
        *,
        risk_pct: float,
        quote: QuoteLike,
        spec: SymbolSpec | None,
        now: datetime,
        market: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Take the CURRENT decision as a paper trade (explicit, idempotent per setup)."""
        if self.fault is not None:
            raise DeskRefusal(*self.fault)  # fail closed: never trade from an untrusted state
        if decision.decision is TradeDecision.WAIT:
            raise DeskRefusal("NOT_ACTIONABLE", "there is no trade plan to take")
        if decision.signal_expiry is not None and now >= decision.signal_expiry:
            raise DeskRefusal("EXPIRED", "the setup has expired")
        if (
            decision.stop_loss is None
            or decision.take_profit is None
            or decision.entry_price is None
        ):
            raise DeskRefusal("NOT_ACTIONABLE", "the plan is incomplete")
        if not decision.setup_id:
            raise DeskRefusal("NOT_ACTIONABLE", "the decision has no setup id")
        if (
            not any(math.isclose(risk_pct, a, abs_tol=1e-9) for a in self.config.allowed_risk)
            or risk_pct > MAX_RISK_PCT
        ):
            raise DeskRefusal(
                "RISK_PCT_NOT_ALLOWED", f"choose one of {list(self.config.allowed_risk)}"
            )
        if any(
            r["setup_id"] == decision.setup_id
            and (
                r["status"] != PaperStatus.CANCELLED
                or r.get("cancel_reason") == "CRASH_BEFORE_COMMIT"
            )
            for r in self.trades.values()
        ):  # a setup that crashed mid-open stays consumed: never a duplicate order
            raise DeskRefusal("DUPLICATE_SETUP", "this setup was already taken")
        if quote.stale:
            raise DeskRefusal("QUOTE_STALE", "the quote is too old to fill against")
        if spec is None:
            raise DeskRefusal("NO_SYMBOL_SPEC", "the broker's symbol specification is unavailable")
        session = str((market or {}).get("session", "?"))
        blockers = self.can_open(now, session, risk_pct, quote)
        if blockers:
            raise DeskRefusal(
                blockers[0], "the paper desk refuses a new trade: " + ", ".join(blockers)
            )
        side = 1 if decision.decision is TradeDecision.BUY else -1
        planned = quote.ask if side > 0 else quote.bid
        equity = self.broker.get_account().equity
        sized = size_for_risk(
            equity, risk_pct, planned, decision.stop_loss, spec, max_risk_pct=MAX_RISK_PCT
        )
        if not sized.allowed:
            raise DeskRefusal(
                "SIZE:" + ",".join(sized.reasons), "the plan cannot be sized at this risk"
            )
        trade_id = f"T{len(self.trades) + 1:05d}"
        record: dict[str, Any] = {
            "trade_id": trade_id,
            "status": PaperStatus.PENDING.value,
            "setup_id": decision.setup_id,
            "decision_id": decision.decision_id,
            "side": decision.decision.value,
            "created_at": _iso(now),
            "source_mode": self.source_mode,
            "session": session,
            "planned_entry": decision.entry_price,
            "quote": {"bid": quote.bid, "ask": quote.ask, "spread_points": quote.spread_points},
            "lots": sized.lots,
            "risk_pct": risk_pct,
            "sl": decision.stop_loss,
            "initial_sl": decision.stop_loss,
            "tp": decision.take_profit,
            "risk_reward_plan": decision.risk_reward,
            "stage": SlStage.INITIAL.value,
            "decision": decision.model_dump(mode="json"),
            "market": market or {},
            "strategy_id": decision.strategy_id,
            "strategy_version": decision.strategy_version,
            "evidence_status": decision.evidence_status.value,
            "code_version": self.code_version,
            "mfe": 0.0,
            "mae": 0.0,
        }
        self.trades[trade_id] = record
        self._journal("paper.pending", record)
        return self._fill(record, decision, quote, now)

    def _fill(
        self, record: dict[str, Any], decision: TradingSignal, quote: QuoteLike, now: datetime
    ) -> dict[str, Any]:
        side = 1 if record["side"] == "BUY" else -1
        self.broker.set_quote(now, bid=quote.bid, spread_points=quote.spread_points)
        slip = self.broker.costs.slippage_points * self.broker.costs.point
        fill_estimate = quote.ask + slip if side > 0 else quote.bid - slip
        sl_distance = abs(record["planned_entry"] - record["initial_sl"])
        drift = abs(fill_estimate - record["planned_entry"])
        if sl_distance > 0 and drift > self.config.max_entry_drift_r * sl_distance:
            return self._cancel(record, "ENTRY_DRIFT", now)
        order = Order(
            order_id=f"paper-{record['setup_id']}",
            symbol=decision.symbol,
            direction=side,
            lots=record["lots"],
            stop_loss=record["sl"],
            take_profit=record["tp"],
            signal_hash=record["decision_id"],
            max_hold_until=now + timedelta(minutes=self.config.max_hold_minutes),
        )
        try:
            position = self.broker.submit_order(order)
        except (
            Exception
        ) as exc:  # a trade must never stay PENDING (it would block its setup forever)
            return self._cancel(record, f"FILL_REJECTED: {type(exc).__name__}: {exc}"[:200], now)
        record.update(
            status=PaperStatus.OPEN.value,
            broker_position=position.model_dump(mode="json"),
            position_id=position.position_id,
            opened_at=_iso(position.entry_time),
            fill_price=position.entry_price,
            max_hold_until=_iso(position.max_hold_until),
            risk_amount=abs(position.entry_price - record["initial_sl"])
            * record["lots"]
            * self.broker.costs.contract_size,
        )
        self.governor.record_open(record["trade_id"], now, record["session"], record["risk_pct"])
        self._journal("paper.open", record)
        self._save()
        return record

    def _cancel(self, record: dict[str, Any], reason: str, now: datetime) -> dict[str, Any]:
        record.update(status=PaperStatus.CANCELLED.value, cancel_reason=reason, closed_at=_iso(now))
        self._journal("paper.cancel", record)
        self._save()
        return record

    # ---- close -------------------------------------------------------------------------------

    def manual_close(
        self, trade_id: str, quote: QuoteLike, now: datetime, reason: str | None = None
    ) -> dict[str, Any]:
        if self.fault is not None:
            raise DeskRefusal(*self.fault)
        rec = self.trades.get(trade_id)
        if rec is None:
            raise DeskRefusal("NOT_FOUND", "no such paper trade")
        if rec["status"] != PaperStatus.OPEN:
            raise DeskRefusal("NOT_OPEN", f"the trade is {rec['status']}, nothing to close")
        self.broker.set_quote(now, bid=quote.bid, spread_points=quote.spread_points)
        why = reason or DeskExit.MANUAL_CLOSE.value
        closed = self.broker.close_position(rec["position_id"], why)
        return self._finalize(rec, closed, why)

    def _finalize(self, rec: dict[str, Any], closed: ClosedTrade, reason: str) -> dict[str, Any]:
        risk_distance = abs(rec["fill_price"] - rec["initial_sl"])
        risk_amount = float(rec.get("risk_amount") or 0.0)
        rec["mfe"], rec["mae"] = self._settled_excursions(rec, closed.exit_price, reason)
        rec.update(
            status=PaperStatus.CLOSED.value,
            broker_closed=closed.model_dump(mode="json"),
            closed_at=_iso(closed.exit_time),
            exit_price=closed.exit_price,
            exit_reason=reason,
            gross_pnl=closed.gross_pnl,
            commission=closed.commission,
            swap=closed.swap,
            net_pnl=closed.net_pnl,
            r_multiple=round(closed.net_pnl / risk_amount, 3) if risk_amount > 0 else None,
            mfe_r=round(rec["mfe"] / risk_distance, 3) if risk_distance > 0 else None,
            mae_r=round(rec["mae"] / risk_distance, 3) if risk_distance > 0 else None,
            duration_minutes=round(
                (closed.exit_time - (_parse(rec["opened_at"]) or closed.exit_time)).total_seconds()
                / 60,
                1,
            ),
        )
        self.governor.record_close(rec["trade_id"], closed.exit_time, closed.net_pnl)
        self._journal("paper.close", rec)
        self._save()
        return rec

    # ---- automatic exits ---------------------------------------------------------------------

    def process_bars(
        self,
        m1: pl.DataFrame,
        *,
        atr: float | None = None,
        swing_low: float | None = None,
        swing_high: float | None = None,
        invalidated: dict[str, bool] | None = None,
    ) -> list[dict[str, Any]]:
        """Apply new CLOSED M1 bars (oldest first) to the open position; returns trades closed."""
        finished: list[dict[str, Any]] = []
        if m1.height == 0 or self.fault is not None:
            return finished  # a faulted or read-only desk changes nothing
        rows = m1.sort("timestamp")
        for row in rows.iter_rows(named=True):
            opened: datetime = row["timestamp"]
            if self.last_bar is not None and opened <= self.last_bar:
                continue
            self.last_bar = opened
            rec = self.open_trade()
            if rec is None:
                continue
            entered = _parse(rec["opened_at"]) or opened
            if opened + timedelta(minutes=1) <= entered:
                continue  # a bar that closed before the entry
            bar = MarketBar(
                time=opened + timedelta(minutes=1),
                open=float(row["open"]),
                high=float(row["high"]),
                low=float(row["low"]),
                close=float(row["close"]),
                spread_points=float(row["spread"]),
            )
            entry_bar = opened < entered
            if entry_bar:
                # the bar that contains the fill mixes pre-entry prices: judge it PESSIMISTICALLY
                # (only the adverse side counts, the favourable extreme is ignored) and never
                # manage the position on it
                bar = self._adverse_only(rec, bar)
            self._track_excursion(rec, bar)  # this bar's range counts even if it closes the trade
            for closed in self.broker.update_market(bar):
                target = next(
                    (r for r in self.trades.values() if r.get("position_id") == closed.position_id),
                    None,
                )
                if target is not None:
                    finished.append(
                        self._finalize(
                            target, closed, _BROKER_REASON.get(closed.reason, closed.reason)
                        )
                    )
            rec = self.open_trade()
            if rec is None or entry_bar:
                continue
            extra = BarExtras(
                atr, swing_low, swing_high, bool((invalidated or {}).get(rec["side"], False))
            )
            closed_now = self._manage(rec, bar, extra)
            if closed_now is not None:
                finished.append(closed_now)
        self._save()
        return finished

    @staticmethod
    def _adverse_only(rec: dict[str, Any], bar: MarketBar) -> MarketBar:
        """The bar of the fill with the favourable side removed (stops can fire, targets cannot)."""
        fill = float(rec["fill_price"])
        if rec["side"] == "BUY":
            return MarketBar(
                time=bar.time, open=fill, high=fill, low=min(bar.low, fill),
                close=min(bar.close, fill), spread_points=bar.spread_points,
            )  # fmt: skip
        return MarketBar(
            time=bar.time, open=fill, high=max(bar.high, fill), low=fill,
            close=max(bar.close, fill), spread_points=bar.spread_points,
        )  # fmt: skip

    def _track_excursion(self, rec: dict[str, Any], bar: MarketBar) -> None:
        spread = bar.spread_points * self.broker.costs.point
        entry = rec["fill_price"]
        if rec["side"] == "BUY":
            favourable, adverse = bar.high - entry, entry - bar.low
        else:
            favourable, adverse = entry - (bar.low + spread), (bar.high + spread) - entry
        rec["mfe_before_bar"], rec["mae_before_bar"] = float(rec["mfe"]), float(rec["mae"])
        rec["mfe"] = max(float(rec["mfe"]), favourable)
        rec["mae"] = max(float(rec["mae"]), adverse)

    @staticmethod
    def _settled_excursions(
        rec: dict[str, Any], exit_price: float, reason: str
    ) -> tuple[float, float]:
        """(MFE, MAE) in price units as they stood when the trade ended.

        The closing bar's range is counted while the trade is open (a trade that ends on its first
        bar still has an excursion), but nothing that happened AFTER the exit may be attributed
        to the trade: a stopped trade cannot have gone further against it than its stop (or the
        gap fill), and a stop is judged before the target, so the favourable extreme of the bar
        that stopped it is not credited. A target exit cannot have gone further for it than the
        target.
        """
        side = 1 if rec["side"] == "BUY" else -1
        mfe, mae = float(rec["mfe"]), float(rec["mae"])
        if reason == DeskExit.STOP_LOSS.value:
            adverse_at_exit = (rec["fill_price"] - exit_price) * side
            mae = min(mae, max(adverse_at_exit, float(rec.get("mae_before_bar", 0.0))))
            mfe = float(rec.get("mfe_before_bar", mfe))
        elif reason == DeskExit.TAKE_PROFIT.value:
            mfe = min(
                mfe,
                max((exit_price - rec["fill_price"]) * side, float(rec.get("mfe_before_bar", 0.0))),
            )
        return mfe, mae

    def _manage(
        self, rec: dict[str, Any], bar: MarketBar, extra: BarExtras
    ) -> dict[str, Any] | None:
        atr, swing_low, swing_high, invalidated = (
            extra.atr, extra.swing_low, extra.swing_high, extra.invalidated,
        )  # fmt: skip
        direction = 1 if rec["side"] == "BUY" else -1
        spread = bar.spread_points * self.broker.costs.point
        position = PositionState(
            ticket=rec["position_id"],
            direction=direction,
            lots=rec["lots"],
            entry=rec["fill_price"],
            initial_sl=rec["initial_sl"],
            sl=rec["sl"],
            tp=rec["tp"],
            opened_at=_parse(rec["opened_at"]) or bar.time,
            stage=SlStage(rec["stage"]),
        )
        # exits are judged on the side a close would trade: bid for a long, ask for a short
        high, low = (bar.high, bar.low) if direction > 0 else (bar.high + spread, bar.low + spread)
        ctx = ManagerContext(
            now=bar.time,
            bar_high=high,
            bar_low=low,
            last_price=bar.close if direction > 0 else bar.close + spread,
            atr=atr,
            swing_low=swing_low,
            swing_high=swing_high,
            highest_since_entry=rec["fill_price"] + rec["mfe"] if direction > 0 else None,
            lowest_since_entry=rec["fill_price"] - rec["mfe"] if direction < 0 else None,
            spread_points=bar.spread_points,
            invalidated=invalidated,
        )
        action = evaluate(position, ctx, self.config.manager)
        if action.kind == "MODIFY_SL" and action.new_sl is not None:
            moved = apply(position, action)
            if moved.sl != position.sl:
                try:
                    self.broker.modify_position(rec["position_id"], stop_loss=moved.sl)
                except ValueError:
                    return (
                        None  # the level is not valid against the current quote: keep the old stop
                    )
                rec.update(sl=moved.sl, stage=moved.stage.value)
                self._journal(
                    "paper.modify",
                    {
                        "trade_id": rec["trade_id"],
                        "sl": moved.sl,
                        "stage": moved.stage.value,
                        "why": action.reason,
                    },
                )
            return None
        if action.kind == "CLOSE":
            reason = (
                DeskExit.INVALIDATED.value if action.reason == "INVALIDATION" else action.reason
            )
            closed = self.broker.close_position(rec["position_id"], reason)
            return self._finalize(rec, closed, reason)
        return None

    # ---- reporting ---------------------------------------------------------------------------

    def day_summary(self, now: datetime) -> dict[str, Any]:
        today = now.astimezone(UTC).date()
        opened_today = [
            r
            for r in self.trades.values()
            if r["status"] != PaperStatus.CANCELLED
            and (_parse(r["created_at"]) or now).astimezone(UTC).date() == today
        ]
        closed = [r for r in opened_today if r["status"] == PaperStatus.CLOSED]
        return {
            "paper_trades": len(opened_today),
            "wins": sum(1 for r in closed if float(r["net_pnl"]) > 0),
            "losses": sum(1 for r in closed if float(r["net_pnl"]) <= 0),
            "open": sum(1 for r in opened_today if r["status"] == PaperStatus.OPEN),
            "net_pnl": round(sum(float(r["net_pnl"]) for r in closed), 2),
            "net_r": round(sum(float(r["r_multiple"] or 0.0) for r in closed), 2),
        }
