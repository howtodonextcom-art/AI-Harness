"""Signal-to-order bridge: the only door from a signal to an order intent (ADR-0019).

The checks run in a fixed order and the first refusal wins. Nothing is written to the persistent
state unless every check passed; the signal is marked as acted on, the decision bar advanced and the
daily counter bumped in ONE transaction, so a crash cannot leave a half-recorded order. Any state
error refuses the signal (fail closed). The bridge sizes through the risk engine and never computes
lots itself, and it never touches a broker.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from xau_edge.execution.order_intent import IntentError, OrderIntent, build_intent
from xau_edge.execution.safety import ExecutionSafety, day_key
from xau_edge.execution.state import (
    DailyLimitError,
    DuplicateSignalError,
    ExecutionState,
    StateError,
)
from xau_edge.observability import log_event
from xau_edge.risk.engine import AccountState, MarketState, RiskEngine, TradeRequest
from xau_edge.signals.schema import Direction, EvidenceStatus, Signal

_LOG = logging.getLogger(__name__)
_PRAGUE = ZoneInfo("Europe/Prague")


@dataclass(frozen=True)
class BridgeResult:
    """Outcome of offering a signal: an intent, or the reasons it was refused."""

    accepted: bool
    reasons: tuple[str, ...]
    intent: OrderIntent | None = None


def _refuse(*reasons: str) -> BridgeResult:
    return BridgeResult(False, reasons)


class SignalBridge:
    """Turns an eligible ``Signal`` into an ``OrderIntent`` after every guard has passed."""

    def __init__(
        self,
        state: ExecutionState,
        risk: RiskEngine,
        safety: ExecutionSafety,
        *,
        magic: int | None,
        dry_run: bool = True,
        hold_bars: int = 20,
        bar_minutes: int = 15,
        max_decision_age: timedelta = timedelta(minutes=30),
    ) -> None:
        self.state = state
        self.risk = risk
        self.safety = safety
        self.magic = magic
        self.dry_run = dry_run or safety.dry_run
        self.hold_bars = hold_bars
        self.bar_minutes = bar_minutes
        self.max_decision_age = max_decision_age

    def process(
        self, signal: Signal, now: datetime, *, account: AccountState, spread_points: float
    ) -> BridgeResult:
        """Offer a signal; returns the intent when accepted, otherwise the first refusal."""
        try:
            result = self._process(signal, now, account, spread_points)
        except StateError as exc:
            log_event(_LOG, "bridge.state_error", logging.ERROR, error=str(exc))
            return _refuse("STATE_UNAVAILABLE")
        if not result.accepted:
            log_event(
                _LOG, "bridge.refused", signal_hash=signal.inputs_hash, reasons=result.reasons
            )
        return result

    def _pre_checks(self, signal: Signal, now: datetime) -> BridgeResult | None:  # noqa: PLR0911
        """Cheap checks that need only the signal and the clock; ``None`` means they all passed."""
        if signal.direction is Direction.WAIT:
            return _refuse(*(tuple(r.value for r in signal.reasons) or ("WAIT",)))
        if signal.evidence_status is not EvidenceStatus.VALIDATED:
            return _refuse("NO_VALIDATED_EDGE")
        if signal.reasons:
            return _refuse(*(r.value for r in signal.reasons))
        if not signal.inputs_hash:
            return _refuse("SIGNAL_NO_HASH")
        if signal.entry_zone is None or signal.stop_loss is None or signal.take_profit_1 is None:
            return _refuse("SIGNAL_INCOMPLETE")
        if signal.signal_expiry is None:
            return _refuse("SIGNAL_NO_EXPIRY")
        if now > signal.signal_expiry:
            return _refuse("SIGNAL_EXPIRED")
        age = now - signal.timestamp
        if age < timedelta(0) or age > self.max_decision_age:
            return _refuse("DECISION_STALE")
        return None

    def _process(  # noqa: PLR0911 - one early exit per refusal, in a fixed order
        self, signal: Signal, now: datetime, account: AccountState, spread_points: float
    ) -> BridgeResult:
        if (refusal := self._pre_checks(signal, now)) is not None:
            return refusal
        # _pre_checks proved these are present; narrow them for the type checker.
        assert signal.entry_zone is not None  # noqa: S101
        assert signal.stop_loss is not None  # noqa: S101
        assert signal.take_profit_1 is not None  # noqa: S101
        if self.magic is None:
            return _refuse("MAGIC_NOT_CONFIGURED")
        if self.state.kill_switch_state()[0] or self.risk.kill_switch.tripped:
            return _refuse("KILL_SWITCH")
        if self.state.is_seen(signal.inputs_hash):
            return _refuse("DUPLICATE_SIGNAL")
        last_bar = self.state.last_decision_bar()
        if last_bar is not None and signal.timestamp <= last_bar:
            return _refuse("DUPLICATE_DECISION_BAR")

        entry = sum(signal.entry_zone) / 2
        if not all(math.isfinite(v) for v in (entry, signal.stop_loss, signal.take_profit_1)):
            return _refuse("SIGNAL_LEVELS_INVALID")
        direction = 1 if signal.direction is Direction.BUY else -1
        if (entry - signal.stop_loss) * direction <= 0:
            return _refuse("SIGNAL_LEVELS_INVALID")

        decision = self.risk.evaluate(
            TradeRequest(
                timestamp=now, direction=direction, stop_distance=abs(entry - signal.stop_loss)
            ),
            account,
            # A BUY/SELL signal cannot exist with a NEWS_* reason (schema), so news is clear here.
            MarketState(
                spread_points=spread_points, regime=signal.market_regime, news_blocked=False
            ),
        )
        if not decision.allowed:
            return _refuse(*decision.reasons)
        day = day_key(now.astimezone(_PRAGUE).date())
        violations = self.safety.violations(
            symbol=signal.symbol, lots=decision.lots, orders_today=self.state.daily_order_count(day)
        )
        if violations:
            return _refuse(*violations)

        try:
            intent = build_intent(
                signal,
                lots=decision.lots,
                risk_amount=decision.risk_amount,
                magic=self.magic,
                created_at=now,
                max_hold_until=now + timedelta(minutes=self.bar_minutes * self.hold_bars),
                dry_run=self.dry_run,
            )
        except IntentError as exc:
            log_event(_LOG, "bridge.intent_invalid", logging.WARNING, error=str(exc))
            return _refuse("SIGNAL_LEVELS_INVALID")
        try:
            self.state.record_accepted(
                signal_hash=signal.inputs_hash,
                intent_id=intent.intent_id,
                decision_time=signal.timestamp,
                day=day,
                dry_run=intent.dry_run,
                max_orders_per_day=self.safety.max_orders_per_day,
                risk_amount=decision.risk_amount,
            )
        except DuplicateSignalError:
            return _refuse("DUPLICATE_SIGNAL")
        except DailyLimitError:
            return _refuse("ORDER_COUNT_EXCEEDED")
        log_event(
            _LOG,
            "bridge.accepted",
            intent_id=intent.intent_id,
            signal_hash=signal.inputs_hash,
            lots=intent.lots,
            dry_run=intent.dry_run,
        )
        return BridgeResult(True, (), intent)
