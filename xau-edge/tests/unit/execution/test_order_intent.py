"""Order intent: deterministic, validated, secret-free, and never built from WAIT."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from tests.unit.signals.test_decision import _inputs
from xau_edge.execution.order_intent import (
    COMMENT_PREFIX,
    IntentError,
    OrderIntent,
    build_intent,
    make_intent_id,
)
from xau_edge.signals.decision import decide
from xau_edge.signals.schema import Direction, EvidenceStatus, Signal

T = datetime(2026, 3, 4, 14, 0, tzinfo=UTC)


def _signal(**over: Any) -> Signal:
    s = decide(_inputs(**over))
    assert s.direction is not Direction.WAIT
    return s


def _build(signal: Signal, **over: Any) -> OrderIntent:
    args: dict[str, Any] = {
        "lots": 0.5,
        "risk_amount": 300.0,
        "magic": 7,
        "created_at": T,
        "max_hold_until": T + timedelta(hours=5),
        "dry_run": True,
    }
    args.update(over)
    return build_intent(signal, **args)


def test_the_same_signal_and_time_give_the_same_intent_id() -> None:
    assert _build(_signal()).intent_id == _build(_signal()).intent_id


def test_a_different_signal_or_time_gives_a_different_intent_id() -> None:
    base = _build(_signal())
    assert _build(_signal(price=2001.0)).intent_id != base.intent_id
    assert _build(_signal(timestamp=T + timedelta(minutes=15))).intent_id != base.intent_id
    assert make_intent_id("h", T) != make_intent_id("h", T + timedelta(seconds=1))


def test_the_intent_uses_the_signals_own_levels() -> None:
    signal = _signal()
    intent = _build(signal)
    assert intent.signal_hash == signal.inputs_hash
    assert intent.direction == 1
    assert intent.stop_loss == signal.stop_loss
    assert intent.take_profit == signal.take_profit_1
    assert intent.entry_reference == pytest.approx(2000.0)
    assert intent.decision_time == signal.timestamp
    assert intent.magic == 7
    assert intent.metadata["evidence_status"] == "VALIDATED"


def test_the_comment_is_traceable_short_and_secret_free() -> None:
    intent = _build(_signal())
    assert intent.comment.startswith(COMMENT_PREFIX)
    assert intent.intent_id[:12] in intent.comment
    assert len(intent.comment) <= 31
    dumped = intent.model_dump_json().lower()
    assert "password" not in dumped
    assert "login" not in dumped


def test_a_wait_signal_never_creates_an_intent() -> None:
    wait = decide(_inputs(evidence_status=EvidenceStatus.NONE))
    with pytest.raises(IntentError, match="WAIT"):
        _build(wait)


def test_a_signal_without_a_hash_or_levels_is_refused() -> None:
    signal = _signal()
    object.__setattr__(signal, "inputs_hash", "")
    with pytest.raises(IntentError, match="inputs_hash"):
        _build(signal)
    signal = _signal()
    object.__setattr__(signal, "stop_loss", None)
    with pytest.raises(IntentError, match="stop loss"):
        _build(signal)
    signal = _signal()
    object.__setattr__(signal, "take_profit_1", None)
    with pytest.raises(IntentError, match="take profit"):
        _build(signal)


def test_inconsistent_levels_are_refused() -> None:
    signal = _signal()
    object.__setattr__(signal, "stop_loss", 2010.0)  # a long stop above the entry
    with pytest.raises(IntentError, match="consistent"):
        _build(signal)
    signal = _signal()
    object.__setattr__(signal, "take_profit_1", float("nan"))
    with pytest.raises(IntentError, match="non-finite"):
        _build(signal)


def test_a_sell_has_the_mirrored_levels() -> None:
    sell = decide(
        _inputs(
            prob_up=0.15,
            prob_down=0.60,
            prob_neutral=0.25,
            htf_bias={"H4": -1, "H1": -1, "M15": -1, "M5": -1},
            analogue_expected_r_long=-0.3,
            analogue_expected_r_short=0.6,
        )
    )
    assert sell.direction is Direction.SELL
    intent = _build(sell)
    assert intent.direction == -1
    assert intent.take_profit < intent.entry_reference < intent.stop_loss


@pytest.mark.parametrize("bad", ["", "x" * 40, "has space", "pass;word"])
def test_unsafe_comments_are_refused(bad: str) -> None:
    good = _build(_signal())
    with pytest.raises(ValueError, match="comment"):
        good.model_copy(update={"comment": bad})


def test_model_copy_revalidates_and_model_construct_is_refused() -> None:
    good = _build(_signal())
    with pytest.raises(ValueError, match="long needs"):
        good.model_copy(update={"stop_loss": good.take_profit + 1})
    with pytest.raises(TypeError):
        OrderIntent.model_construct()  # type: ignore[call-arg]


def test_naive_timestamps_and_hold_before_decision_are_refused() -> None:
    signal = _signal()
    with pytest.raises(IntentError):
        _build(signal, created_at=datetime(2026, 3, 4, 14, 0))  # noqa: DTZ001
    with pytest.raises(IntentError, match="max_hold_until"):
        _build(signal, max_hold_until=T - timedelta(minutes=1))


def test_non_positive_or_non_finite_lots_are_refused() -> None:
    signal = _signal()
    for lots in (0.0, -1.0, float("nan"), float("inf")):
        with pytest.raises(IntentError):
            _build(signal, lots=lots)


def test_to_order_maps_onto_the_broker_neutral_order() -> None:
    intent = _build(_signal())
    order = intent.to_order()
    assert order.order_id == intent.intent_id
    assert order.signal_hash == intent.signal_hash
    assert order.stop_loss == intent.stop_loss
    assert order.take_profit == intent.take_profit
    assert order.lots == intent.lots
    assert order.max_hold_until == intent.max_hold_until
