"""MT5 DEMO executor: the only code in the project that can send an order (ADR-0019).

Every order passes the same gates, in this order, and ANY failure refuses the order:

1. configuration: demo trading enabled, dry-run off, an explicit account whitelist and magic number;
2. the intent itself: not a dry-run intent, bot magic, whitelisted symbol, lots within the maximum,
   finite levels on the correct side of the entry;
3. the persistent kill switch is clear;
4. the terminal account is a DEMO account on the whitelist, trading is allowed;
5. a fresh reconciliation of broker against state is clean (a mismatch trips the kill switch);
6. the symbol allows trading, the volume fits the symbol's limits, the price has not moved more
   than the deviation limit from the signal's entry;
7. exactly-once: a submission row is created atomically BEFORE sending, so the same intent can
   never be sent twice, not even after a crash;
8. the broker's own ``order_check`` accepts the request.

Only then ``_guarded_send`` calls ``order_send``: it is the single place in the package that does,
and a test enforces that. If the outcome cannot be proven (no answer, an exception, a position that
cannot be found afterwards) the kill switch is tripped and nothing is retried.

Closing is limited to positions the bot opened (state + magic) and is allowed while the kill switch
is tripped, because closing reduces risk; opening is not.
"""

from __future__ import annotations

import contextlib
import logging
import math
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Literal

from xau_edge.brokers.mt5_demo.reader import DemoAccountError, DemoReader
from xau_edge.execution.journal import ExecutionJournal
from xau_edge.execution.order_intent import COMMENT_PREFIX, OrderIntent, make_intent_id
from xau_edge.execution.reconcile import BrokerPosition, Reconciler
from xau_edge.execution.runner import JournalError
from xau_edge.execution.state import (
    BotPositionRecord,
    DuplicateSubmissionError,
    ExecutionState,
    StateError,
)
from xau_edge.observability import log_event

_LOG = logging.getLogger(__name__)

_TRADE_NAMES = frozenset(
    {
        "order_send",
        "order_check",
        "positions_get",
        "symbol_info",
        "symbol_info_tick",
        "account_info",
        "last_error",
        "ACCOUNT_TRADE_MODE_DEMO",
        "POSITION_TYPE_BUY",
        "POSITION_TYPE_SELL",
        "TRADE_ACTION_DEAL",
        "ORDER_TYPE_BUY",
        "ORDER_TYPE_SELL",
        "ORDER_TIME_GTC",
        "ORDER_FILLING_FOK",
        "ORDER_FILLING_IOC",
        "ORDER_FILLING_RETURN",
        "SYMBOL_FILLING_FOK",
        "SYMBOL_FILLING_IOC",
        "SYMBOL_TRADE_MODE_FULL",
        "TRADE_RETCODE_DONE",
        "TRADE_RETCODE_PLACED",
    }
)
RETCODE_PARTIAL = 10010
DEFINITE_REJECTS = frozenset(
    {
        10004, 10006, 10013, 10014, 10015, 10016, 10017, 10018, 10019, 10020, 10021, 10022,
        10025, 10026, 10027, 10028, 10029, 10030, 10033, 10034, 10035, 10036, 10038, 10039,
        10040, 10041, 10042, 10043, 10044,
    }
)  # fmt: skip
"""Codes that prove the order did NOT execute. Anything else that is not a fill is ambiguous
(timeouts, lost connection, too many requests) and is resolved by looking the position up."""
CLOSE_COMMENT = f"{COMMENT_PREFIX}CLOSE"
SMOKE_COMMENT = f"{COMMENT_PREFIX}SMOKE"

Status = Literal["FILLED", "REJECTED", "REFUSED", "UNKNOWN"]


@dataclass(frozen=True)
class ExecutorConfig:
    """Everything the executor needs to know; built from ``Settings`` by the caller."""

    enabled: bool
    dry_run: bool
    allowed_accounts: tuple[str, ...]
    symbols: tuple[str, ...]
    magic: int | None
    max_lots: float
    deviation_points: int = 30
    smoke: bool = False
    max_tick_age_seconds: int = 60
    max_intent_age: timedelta = timedelta(minutes=45)
    max_open_positions: int = 1


@dataclass(frozen=True)
class SubmitResult:
    """Outcome of an attempt to send or close."""

    status: Status
    reasons: tuple[str, ...]
    ticket: str | None = None
    retcode: int | None = None


def _refused(*reasons: str) -> SubmitResult:
    return SubmitResult("REFUSED", reasons)


class TradeMt5:
    """Allowlist proxy over the terminal for the executor (an accident guard, not a sandbox)."""

    def __init__(self, client: Any) -> None:
        self._inner = client

    def __getattr__(self, name: str) -> Any:
        if name in _TRADE_NAMES:
            return getattr(self._inner, name)
        msg = f"{name!r} is not available on the executor's MT5 client"
        raise AttributeError(msg)


class Mt5DemoExecutor:
    """Sends, and closes, bot-owned orders on a DEMO account behind every gate."""

    def __init__(  # noqa: PLR0917 - explicit collaborators, no hidden globals
        self,
        client: Any,
        reader: DemoReader,
        state: ExecutionState,
        journal: ExecutionJournal,
        reconciler: Reconciler,
        config: ExecutorConfig,
    ) -> None:
        self._mt5 = TradeMt5(client)
        self.reader = reader
        self.state = state
        self.journal = journal
        self.reconciler = reconciler
        self.config = config

    # -- opening ------------------------------------------------------------------------------

    def submit(self, intent: OrderIntent, now: datetime) -> SubmitResult:
        """Send the order for a bridge-approved intent, or refuse it."""
        return self._open(intent, now, smoke=False)

    def submit_smoke(self, intent: OrderIntent, now: datetime) -> SubmitResult:
        """Send ONE labelled minimum-lot pipeline test order (needs the smoke switch)."""
        if not self.config.smoke:
            return _refused("SMOKE_DISABLED")
        if intent.comment != SMOKE_COMMENT:
            return _refused("NOT_A_SMOKE_INTENT")
        return self._open(intent, now, smoke=True)

    def _open(self, intent: OrderIntent, now: datetime, *, smoke: bool) -> SubmitResult:
        try:
            reasons = self._gates(intent, now, smoke=smoke)
            if reasons:
                self.journal.record("order.refused", intent_id=intent.intent_id, reasons=reasons)
                return _refused(*reasons)
            request, price_reason = self._build_request(intent, now)
            if request is None:
                self.journal.record(
                    "order.refused", intent_id=intent.intent_id, reasons=[price_reason]
                )
                return _refused(price_reason)
            self.journal.record(
                "order.requested", intent_id=intent.intent_id, signal_hash=intent.signal_hash,
                lots=intent.lots, direction=intent.direction, smoke=smoke,
            )  # fmt: skip
            self.state.begin_submission(intent.intent_id, intent.signal_hash)
        except DuplicateSubmissionError:
            self._record_quietly(
                "order.refused", intent_id=intent.intent_id, reasons=["DUPLICATE_SUBMISSION"]
            )
            return _refused("DUPLICATE_SUBMISSION")
        except (StateError, JournalError, DemoAccountError) as exc:
            log_event(_LOG, "executor.refused_on_error", logging.ERROR, error=str(exc))
            return _refused("EXECUTOR_ERROR")
        late = self._recheck(intent)
        if late:
            return late
        return self._send_and_record(intent, request)

    def _recheck(self, intent: OrderIntent) -> SubmitResult | None:
        """Last look right before sending: the world may have changed since the gates ran."""
        try:
            reasons: list[str] = []
            if self.state.kill_switch_state()[0]:
                reasons.append("KILL_SWITCH")
            account = self.reader.account()
            if account.account_id not in self.config.allowed_accounts:
                reasons.append("ACCOUNT_NOT_WHITELISTED")
            if not account.trade_allowed:
                reasons.append("TRADING_NOT_ALLOWED")
            if not reasons:
                return None
            self.state.finish_submission(intent.intent_id, "REJECTED")
            self.journal.record("order.refused", intent_id=intent.intent_id, reasons=reasons)
            return _refused(*reasons)
        except (StateError, JournalError, DemoAccountError) as exc:
            log_event(_LOG, "executor.recheck_failed", logging.ERROR, error=str(exc))
            with contextlib.suppress(StateError):
                self.state.finish_submission(intent.intent_id, "REJECTED")
            return _refused("EXECUTOR_ERROR")

    def _gates(  # noqa: PLR0912
        self, intent: OrderIntent, now: datetime, *, smoke: bool
    ) -> list[str]:
        cfg = self.config
        reasons: list[str] = []
        if not cfg.enabled:
            reasons.append("DEMO_TRADING_DISABLED")
        if cfg.dry_run:
            reasons.append("DRY_RUN")
        if not cfg.allowed_accounts:
            reasons.append("NO_ACCOUNT_WHITELIST")
        if cfg.magic is None:
            reasons.append("MAGIC_NOT_CONFIGURED")
        if reasons:
            return reasons
        if intent.dry_run:
            reasons.append("INTENT_IS_DRY_RUN")
        if intent.magic != cfg.magic:
            reasons.append("MAGIC_MISMATCH")
        if intent.symbol not in cfg.symbols:
            reasons.append("SYMBOL_NOT_WHITELISTED")
        if not math.isfinite(intent.lots) or not 0 < intent.lots <= cfg.max_lots:
            reasons.append("LOTS_ABOVE_MAXIMUM")
        if smoke and intent.lots > 0.01 + 1e-12:
            reasons.append("SMOKE_LOT_TOO_LARGE")
        if not smoke and not self.state.is_approved(intent.intent_id):
            reasons.append("NOT_APPROVED_BY_BRIDGE")
        if now >= intent.max_hold_until:
            reasons.append("INTENT_EXPIRED")
        if now - intent.decision_time > cfg.max_intent_age:
            reasons.append("INTENT_STALE")
        if len(self.state.open_positions()) >= cfg.max_open_positions:
            reasons.append("BOT_POSITION_ALREADY_OPEN")
        if self.state.kill_switch_state()[0]:
            reasons.append("KILL_SWITCH")
        if reasons:
            return reasons
        account = self.reader.account()
        if account.account_id not in cfg.allowed_accounts:
            reasons.append("ACCOUNT_NOT_WHITELISTED")
        if not account.trade_allowed:
            reasons.append("TRADING_NOT_ALLOWED")
        if reasons:
            return reasons
        snapshot = self.reader.snapshot(datetime.now().astimezone())
        rec = self.reconciler.check(snapshot)
        if not rec.clean:
            reasons.extend(f"RECONCILE_{c}" for c in rec.codes)
        return reasons

    def _build_request(  # noqa: PLR0911 - one early exit per refusal reason
        self, intent: OrderIntent, now: datetime
    ) -> tuple[dict[str, Any] | None, str]:
        mt5 = self._mt5
        info = mt5.symbol_info(intent.symbol)
        tick = mt5.symbol_info_tick(intent.symbol)
        if info is None or tick is None:
            return None, "SYMBOL_UNAVAILABLE"
        if info.trade_mode != mt5.SYMBOL_TRADE_MODE_FULL:
            return None, "SYMBOL_NOT_TRADABLE"
        step = float(info.volume_step)
        if not (float(info.volume_min) <= intent.lots <= float(info.volume_max)) or step <= 0:
            return None, "VOLUME_OUT_OF_RANGE"
        if abs(intent.lots / step - round(intent.lots / step)) > 1e-6:
            return None, "VOLUME_NOT_ON_STEP"
        tick_age = now - self.reader.utc_from_epoch(int(tick.time))
        if tick_age.total_seconds() > self.config.max_tick_age_seconds:
            return None, "TICK_STALE"
        price = float(tick.ask if intent.direction == 1 else tick.bid)
        if not math.isfinite(price) or price <= 0:
            return None, "PRICE_INVALID"
        limit = self.config.deviation_points * float(info.point)
        if abs(price - intent.entry_reference) > limit:
            return None, "ENTRY_PRICE_MOVED"
        flags = int(info.filling_mode)
        if flags & mt5.SYMBOL_FILLING_FOK:
            filling = mt5.ORDER_FILLING_FOK
        elif flags & mt5.SYMBOL_FILLING_IOC:
            filling = mt5.ORDER_FILLING_IOC
        else:
            filling = mt5.ORDER_FILLING_RETURN
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": intent.symbol,
            "volume": intent.lots,
            "type": mt5.ORDER_TYPE_BUY if intent.direction == 1 else mt5.ORDER_TYPE_SELL,
            "price": price,
            "sl": intent.stop_loss,
            "tp": intent.take_profit,
            "deviation": self.config.deviation_points,
            "magic": intent.magic,
            "comment": intent.comment,
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": filling,
        }
        return request, ""

    def _guarded_send(self, request: dict[str, Any]) -> Any:
        """The single call site of ``order_send``; callers must have passed every gate."""
        return self._mt5.order_send(request)

    def _send_and_record(  # noqa: PLR0911 - one exit per outcome
        self, intent: OrderIntent, request: dict[str, Any]
    ) -> SubmitResult:
        mt5 = self._mt5
        try:
            check = mt5.order_check(request)
            if check is None or int(check.retcode) != 0:
                code = None if check is None else int(check.retcode)
                self.state.finish_submission(intent.intent_id, "REJECTED", retcode=code)
                self.journal.record("order.check_failed", intent_id=intent.intent_id, retcode=code)
                return SubmitResult("REJECTED", ("ORDER_CHECK_FAILED",), retcode=code)
        except (StateError, JournalError):
            return self._unknown(intent, "state or journal failed around order_check")
        except Exception as exc:
            return self._unknown(intent, f"order_check raised {type(exc).__name__}")
        try:
            result = self._guarded_send(request)
        except Exception as exc:
            return self._resolve_uncertain(intent, f"order_send raised {type(exc).__name__}")
        if result is None:
            return self._resolve_uncertain(intent, "order_send returned no answer")
        try:
            retcode = int(result.retcode)
            order_id = getattr(result, "order", None)
            self._record_quietly("order.answered", intent_id=intent.intent_id, retcode=retcode)
            fills = (mt5.TRADE_RETCODE_DONE, mt5.TRADE_RETCODE_PLACED, RETCODE_PARTIAL)
            if retcode in fills:
                return self._confirm_fill(intent, retcode, order_id)
            if retcode in DEFINITE_REJECTS:
                self.state.finish_submission(intent.intent_id, "REJECTED", retcode=retcode)
                return SubmitResult("REJECTED", ("BROKER_REJECTED",), retcode=retcode)
            return self._resolve_uncertain(intent, f"ambiguous broker answer {retcode}")
        except Exception as exc:
            return self._resolve_uncertain(
                intent, f"post-send handling raised {type(exc).__name__}"
            )

    def _resolve_uncertain(self, intent: OrderIntent, why: str) -> SubmitResult:
        """No clear answer: look the position up by magic and comment; unproven means stop."""
        try:
            found = self._find_position(intent.comment, intent.magic, None)
        except DemoAccountError:
            found = None
        if found is None:
            return self._unknown(intent, why)
        return self._confirm_fill(intent, -1, found.ticket)

    def _confirm_fill(self, intent: OrderIntent, retcode: int, order_id: Any) -> SubmitResult:
        try:
            position = self._find_position(intent.comment, intent.magic, order_id)
        except DemoAccountError:
            position = None
        if position is None:
            return self._unknown(intent, "the position could not be found after the order")
        try:
            self.state.register_position(
                BotPositionRecord(
                    intent_id=intent.intent_id,
                    ticket=position.ticket,
                    symbol=position.symbol,
                    direction=intent.direction,
                    lots=position.lots,
                    stop_loss=intent.stop_loss,  # what we asked for: reconciliation compares
                    take_profit=intent.take_profit,  # the broker against it, not against itself
                    opened_at=position.opened_at,
                    max_hold_until=intent.max_hold_until,
                )
            )
            self.state.finish_submission(
                intent.intent_id, "FILLED", retcode=retcode, ticket=position.ticket
            )
        except StateError:
            return self._unknown(intent, "could not record the filled position")
        self._record_quietly(
            "position.opened",
            intent_id=intent.intent_id,
            ticket=position.ticket,
            lots=position.lots,
        )
        if not self._protection_matches(intent, position):
            log_event(_LOG, "executor.protection_missing", logging.CRITICAL, ticket=position.ticket)
            self.close_position(position.ticket, "PROTECTION_MISMATCH")
            with contextlib.suppress(StateError):
                self.state.trip_kill_switch("PROTECTION_MISMATCH: stop or target not as ordered")
            return SubmitResult(
                "FILLED", ("PROTECTION_MISMATCH",), ticket=position.ticket, retcode=retcode
            )
        return SubmitResult("FILLED", (), ticket=position.ticket, retcode=retcode)

    @staticmethod
    def _protection_matches(intent: OrderIntent, position: BrokerPosition) -> bool:
        tolerance = 0.011
        return (
            position.direction == intent.direction
            and abs(position.stop_loss - intent.stop_loss) <= tolerance
            and abs(position.take_profit - intent.take_profit) <= tolerance
        )

    def _find_position(self, comment: str, magic: int, order_id: Any) -> BrokerPosition | None:
        for position in self.reader.positions():
            if position.magic != magic:
                continue
            if position.comment.startswith(comment) or position.ticket == str(order_id):
                return position
        return None

    def _unknown(self, intent: OrderIntent, why: str) -> SubmitResult:
        """The outcome cannot be proven: stop everything and never retry blindly."""
        log_event(_LOG, "executor.unknown_state", logging.CRITICAL, reason=why)
        with contextlib.suppress(StateError):  # a PENDING row is also "unresolved" to reconcile
            self.state.finish_submission(intent.intent_id, "UNKNOWN")
        try:
            self.state.trip_kill_switch(f"UNKNOWN_ORDER_STATE: {why}")
        except StateError as exc:
            log_event(_LOG, "executor.trip_failed", logging.CRITICAL, error=str(exc))
        self._record_quietly("order.unknown", intent_id=intent.intent_id, why=why)
        return SubmitResult("UNKNOWN", ("UNKNOWN_ORDER_STATE",))

    def _record_quietly(self, event: str, **fields: Any) -> None:
        """Journal an event AFTER the action happened: a failure here must not hide the action."""
        try:
            self.journal.record(event, **fields)
        except JournalError as exc:
            log_event(_LOG, "executor.journal_failed", logging.ERROR, error=str(exc))

    # -- closing ------------------------------------------------------------------------------

    def close_position(  # noqa: PLR0911 - one exit per refusal or outcome
        self, ticket: str, reason: str
    ) -> SubmitResult:
        """Close a bot-owned position (allowed while the kill switch is tripped)."""
        cfg = self.config
        try:
            if (
                not (cfg.enabled and not cfg.dry_run)
                or not cfg.allowed_accounts
                or cfg.magic is None
            ):
                return _refused("DEMO_TRADING_DISABLED")
            account = self.reader.account()
            if account.account_id not in cfg.allowed_accounts:
                return _refused("ACCOUNT_NOT_WHITELISTED")
            owned = {r.ticket: r for r in self.state.open_positions()}
            if ticket not in owned:
                return _refused("NOT_A_BOT_POSITION")
            position = next((p for p in self.reader.positions() if p.ticket == ticket), None)
            if position is None or position.magic != cfg.magic:
                return _refused("NOT_A_BOT_POSITION")
            request = self._close_request(position)
            if request is None:
                return _refused("SYMBOL_UNAVAILABLE")
            self.journal.record("position.closing", ticket=ticket, reason=reason)
        except (StateError, JournalError, DemoAccountError) as exc:
            log_event(_LOG, "executor.close_refused_on_error", logging.ERROR, error=str(exc))
            return _refused("EXECUTOR_ERROR")
        try:
            result = self._guarded_send(request)
        except Exception as exc:
            return self._close_unknown(ticket, f"order_send raised {type(exc).__name__}")
        if result is None:
            return self._close_unknown(ticket, "order_send returned no answer")
        retcode = int(result.retcode)
        if retcode not in (self._mt5.TRADE_RETCODE_DONE, self._mt5.TRADE_RETCODE_PLACED):
            self._record_quietly("position.close_rejected", ticket=ticket, retcode=retcode)
            return SubmitResult("REJECTED", ("BROKER_REJECTED",), ticket=ticket, retcode=retcode)
        try:
            still_open = any(p.ticket == ticket for p in self.reader.positions())
        except DemoAccountError:
            return self._close_unknown(ticket, "could not verify the close")
        if still_open:
            return self._close_unknown(ticket, "the position is still open after the close")
        try:
            self.state.mark_position_closed(ticket)
        except StateError:
            return self._close_unknown(ticket, "could not record the close")
        self._record_quietly("position.closed", ticket=ticket, reason=reason)
        return SubmitResult("FILLED", (), ticket=ticket, retcode=retcode)

    def _close_request(self, position: BrokerPosition) -> dict[str, Any] | None:
        mt5 = self._mt5
        info = mt5.symbol_info(position.symbol)
        tick = mt5.symbol_info_tick(position.symbol)
        if info is None or tick is None:
            return None
        flags = int(info.filling_mode)
        if flags & mt5.SYMBOL_FILLING_FOK:
            filling = mt5.ORDER_FILLING_FOK
        elif flags & mt5.SYMBOL_FILLING_IOC:
            filling = mt5.ORDER_FILLING_IOC
        else:
            filling = mt5.ORDER_FILLING_RETURN
        closing_a_long = position.direction == 1
        return {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": position.symbol,
            "volume": position.lots,
            "type": mt5.ORDER_TYPE_SELL if closing_a_long else mt5.ORDER_TYPE_BUY,
            "position": int(position.ticket),
            "price": float(tick.bid if closing_a_long else tick.ask),
            "deviation": self.config.deviation_points,
            "magic": int(self.config.magic or 0),
            "comment": CLOSE_COMMENT,
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": filling,
        }

    def _close_unknown(self, ticket: str, why: str) -> SubmitResult:
        log_event(_LOG, "executor.close_unknown", logging.CRITICAL, reason=why)
        try:
            self.state.trip_kill_switch(f"UNKNOWN_CLOSE_STATE: {why}")
        except StateError as exc:
            log_event(_LOG, "executor.trip_failed", logging.CRITICAL, error=str(exc))
        self._record_quietly("position.close_unknown", ticket=ticket, why=why)
        return SubmitResult("UNKNOWN", ("UNKNOWN_CLOSE_STATE",), ticket=ticket)

    def close_expired(self, now: datetime) -> list[SubmitResult]:
        """Close every bot position whose ``max_hold_until`` has passed."""
        results: list[SubmitResult] = []
        for record in self.state.open_positions():
            if record.max_hold_until <= now:
                results.append(self.close_position(record.ticket, "MAX_HOLD_EXPIRED"))
        return results


def build_smoke_intent(
    ask: float, now: datetime, *, magic: int, symbol: str = "XAUUSD", lots: float = 0.01
) -> OrderIntent:
    """The labelled minimum-lot BUY used to test the order pipeline (never from a signal)."""
    tag = f"SMOKE-{now:%Y%m%dT%H%M%S}"
    return OrderIntent(
        intent_id=make_intent_id(tag, now),
        signal_hash=tag,
        symbol=symbol,
        direction=1,
        lots=lots,
        risk_amount=0.0,
        entry_reference=ask,
        stop_loss=round(ask - 15.0, 2),
        take_profit=round(ask + 30.0, 2),
        max_hold_until=now + timedelta(minutes=5),
        decision_time=now,
        created_at=now,
        magic=magic,
        comment=SMOKE_COMMENT,
        dry_run=False,
        metadata={"purpose": "pipeline smoke test, not evidence"},
    )
