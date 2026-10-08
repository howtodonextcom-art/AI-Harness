"""The owner override (decision D2) in the bridge, and the shadow tier in the executor."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from tests.unit.brokers.test_executor import _make
from tests.unit.execution.test_bridge import PROP, T, _account
from tests.unit.signals.test_decision import _inputs
from xau_edge.execution.bridge import BridgeResult, SignalBridge
from xau_edge.execution.order_intent import COMMENT_PREFIX
from xau_edge.execution.override import OverridePolicy
from xau_edge.execution.safety import ExecutionSafety
from xau_edge.execution.state import ExecutionState, PersistentKillSwitch
from xau_edge.risk.engine import RiskEngine, RiskLimits
from xau_edge.signals.decision import decide
from xau_edge.signals.schema import Direction, EvidenceStatus, NoTradeReason, Signal

STRATEGY = "h03_london_open"


def _bridge(
    folder: Path,
    override: OverridePolicy | None,
    *,
    lot_cap: float | None = None,
    dry_run: bool = True,
) -> SignalBridge:
    state = ExecutionState(folder / "s.sqlite")
    risk = RiskEngine(RiskLimits(risk_per_trade_pct=0.25), PROP, PersistentKillSwitch(state))
    return SignalBridge(
        state,
        risk,
        ExecutionSafety(dry_run=dry_run),
        magic=7,
        dry_run=dry_run,
        override=override,
        lot_cap=lot_cap,
    )


def _unvalidated(**over: Any) -> Signal:
    """The case D2 is about: WAIT with only NO_VALIDATED_EDGE, a BUY lean and its levels."""
    signal = decide(_inputs(evidence_status=EvidenceStatus.NONE, **over))
    assert signal.direction is Direction.WAIT
    return signal


def _offer(bridge: SignalBridge, signal: Signal, strategy_id: str | None) -> BridgeResult:
    return bridge.process(
        signal, T, account=_account(), spread_points=30.0, strategy_id=strategy_id
    )


def test_the_d2_signal_carries_only_the_missing_evidence_reason() -> None:
    signal = _unvalidated()
    assert signal.reasons == (NoTradeReason.NO_VALIDATED_EDGE,)
    assert signal.candidate_direction is Direction.BUY


@pytest.mark.parametrize(
    "override",
    [None, OverridePolicy(enabled=False, strategy_id=STRATEGY), OverridePolicy(True, "")],
    ids=["no-policy", "disabled", "no-strategy"],
)
def test_without_an_enabled_override_the_evidence_gate_refuses(
    tmp_path: Path, override: OverridePolicy | None
) -> None:
    bridge = _bridge(tmp_path, override)
    result = _offer(bridge, _unvalidated(), STRATEGY)
    assert not result.accepted
    assert result.reasons == ("NO_VALIDATED_EDGE",)
    assert not bridge.state.is_seen(_unvalidated().inputs_hash)


@pytest.mark.parametrize("strategy_id", [None, "baseline_c", "h03_london_open_v2"])
def test_a_signal_from_another_strategy_is_refused(tmp_path: Path, strategy_id: str | None) -> None:
    bridge = _bridge(tmp_path, OverridePolicy(enabled=True, strategy_id=STRATEGY))
    result = _offer(bridge, _unvalidated(), strategy_id)
    assert result.reasons == ("NO_VALIDATED_EDGE",)


@pytest.mark.parametrize(
    ("over", "reason"),
    [
        ({"news_blocked": None}, "NEWS_UNKNOWN"),
        ({"news_blocked": True}, "NEWS_RISK"),
        ({"regime": "SHOCK"}, "REGIME_UNSUPPORTED"),
        ({"spread_points": 500.0}, "SPREAD_EXCESSIVE"),
    ],
)
def test_any_other_refusal_reason_still_blocks_with_the_override_on(
    tmp_path: Path, over: dict[str, Any], reason: str
) -> None:
    bridge = _bridge(tmp_path, OverridePolicy(enabled=True, strategy_id=STRATEGY))
    signal = _unvalidated(**over)
    assert reason in {r.value for r in signal.reasons}
    result = _offer(bridge, signal, STRATEGY)
    assert not result.accepted
    assert reason in result.reasons
    assert result.intent is None
    assert not bridge.state.is_seen(signal.inputs_hash)


def test_the_override_with_the_named_strategy_makes_a_labelled_intent(tmp_path: Path) -> None:
    bridge = _bridge(tmp_path, OverridePolicy(enabled=True, strategy_id=STRATEGY))
    result = _offer(bridge, _unvalidated(), STRATEGY)
    assert result.accepted
    intent = result.intent
    assert intent is not None
    assert intent.direction == 1
    assert intent.comment.startswith(f"{COMMENT_PREFIX}UNV:")
    assert intent.metadata["evidence_status"] == "UNVALIDATED_OVERRIDE"
    assert intent.metadata["strategy_id"] == STRATEGY
    # sized at 0.25%: 250 / (7.8 * 100) = 0.32 lots
    assert intent.lots == pytest.approx(0.32)
    assert bridge.state.is_seen(_unvalidated().inputs_hash)


def test_the_override_still_obeys_the_kill_switch(tmp_path: Path) -> None:
    bridge = _bridge(tmp_path, OverridePolicy(enabled=True, strategy_id=STRATEGY))
    bridge.state.trip_kill_switch("test")
    assert _offer(bridge, _unvalidated(), STRATEGY).reasons == ("KILL_SWITCH",)


def test_the_tier_lot_cap_is_applied_to_the_override_intent(tmp_path: Path) -> None:
    bridge = _bridge(tmp_path, OverridePolicy(enabled=True, strategy_id=STRATEGY), lot_cap=0.01)
    result = _offer(bridge, _unvalidated(), STRATEGY)
    assert result.intent is not None
    assert result.intent.lots == pytest.approx(0.01)
    assert result.intent.risk_amount == pytest.approx(0.01 * 7.8 * 100)


def test_the_shadow_executor_checks_the_order_but_never_sends_it(tmp_path: Path) -> None:
    bridge = _bridge(
        tmp_path, OverridePolicy(enabled=True, strategy_id=STRATEGY), lot_cap=0.01, dry_run=False
    )
    result = _offer(bridge, _unvalidated(), STRATEGY)
    assert result.intent is not None
    assert result.intent.dry_run is False
    executor, term = _make(tmp_path, shadow=True)  # shares s.sqlite with the bridge
    outcome = executor.submit(result.intent, T)
    assert outcome.status == "SHADOW"
    assert outcome.reasons == ("SHADOW_TIER_NOT_SENT",)
    assert term.sent == []  # order_send was never called
    assert len(term.checked) == 1  # the broker's order_check ran
    assert term.checked[0]["comment"].startswith(f"{COMMENT_PREFIX}UNV:")
    assert executor.state.open_positions() == []
    events = [e["event"] for e in executor.journal.read()]
    assert "order.shadow_checked" in events
