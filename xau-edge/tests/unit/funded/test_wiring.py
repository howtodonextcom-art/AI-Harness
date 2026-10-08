"""From a RunPlan to collaborators: limits, real-account safety, executor, shadow days, status."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import pytest

from tests.unit.brokers.test_executor import _intent, _make
from tests.unit.execution.test_bridge import PROP, _account
from xau_edge.execution.override import OverridePolicy
from xau_edge.execution.state import ExecutionState
from xau_edge.experiments.registry import ExperimentRegistry
from xau_edge.funded.identity import RunMode
from xau_edge.funded.plan import RunPlan
from xau_edge.funded.rollout import RolloutController, load_rollout
from xau_edge.funded.wiring import (
    PropFacts,
    alert_fn,
    execution_safety,
    executor_config,
    make_submit,
    risk_limits,
    rollout_announcement,
    strategy_validated,
)
from xau_edge.ops.notifier import AlertDispatcher, AlertEvent
from xau_edge.signals.strategy_registry import StrategySpec

ROOT = Path(__file__).parents[3]
T = datetime(2026, 3, 4, 14, 0, tzinfo=UTC)

FUNDED_SHADOW = RunPlan(
    mode=RunMode.FUNDED,
    magic=7,
    allowed_accounts=("555",),
    initial_capital=100_000.0,
    prop_profile_source="configs/prop/ftmo_funded.yaml",
    state_path=Path("f.sqlite"),
    journal_path=Path("f.jsonl"),
    send_orders=False,
    shadow=True,
    lot_cap=None,
    max_lots=1.0,
    risk_pct=0.25,
    override=OverridePolicy(enabled=True, strategy_id="h03"),
    strategy_id="h03",
    evidence_label="UNVALIDATED",
    require_demo=False,
    rollout_tier=0,
    rollout_tier_name="shadow",
)
DRY = replace(
    FUNDED_SHADOW,
    mode=RunMode.DRY_RUN,
    shadow=False,
    override=None,
    strategy_id=None,
    evidence_label="NONE",
    require_demo=True,
    rollout_tier=None,
    rollout_tier_name=None,
    risk_pct=0.5,
)


def test_risk_limits_use_the_plans_risk_and_lot_limit() -> None:
    limits = risk_limits(replace(FUNDED_SHADOW, max_lots=0.5))
    assert limits.risk_per_trade_pct == 0.25
    assert limits.max_lot == 0.5
    assert limits.max_total_lots == 0.5


def test_execution_safety_checks_the_real_environment_and_account_not_paper() -> None:
    safety = execution_safety(
        FUNDED_SHADOW, account="555", symbols=("XAUUSD",), max_orders_per_day=1
    )
    assert safety.environment == "funded"
    assert safety.account == "555"
    assert safety.dry_run is False
    assert safety.violations(symbol="XAUUSD", lots=0.1, orders_today=0) == []
    wrong = execution_safety(
        FUNDED_SHADOW, account="111", symbols=("XAUUSD",), max_orders_per_day=1
    )
    assert "ACCOUNT_NOT_WHITELISTED" in wrong.violations(symbol="XAUUSD", lots=0.1, orders_today=0)
    assert execution_safety(DRY, account="555", symbols=("XAUUSD",), max_orders_per_day=1).dry_run


def test_no_executor_without_sending_or_shadowing_and_the_tier_cap_bounds_its_lots() -> None:
    assert executor_config(DRY, symbols=("XAUUSD",), deviation_points=60) is None
    shadow = executor_config(FUNDED_SHADOW, symbols=("XAUUSD",), deviation_points=60)
    assert shadow is not None
    assert shadow.shadow is True
    assert shadow.enabled is True
    assert shadow.dry_run is False
    assert shadow.magic == 7
    minimum = executor_config(
        replace(FUNDED_SHADOW, send_orders=True, shadow=False, lot_cap=0.01),
        symbols=("XAUUSD",),
        deviation_points=60,
    )
    assert minimum is not None
    assert minimum.shadow is False
    assert minimum.max_lots == 0.01


def test_a_shadow_result_counts_the_prague_day_for_the_rollout(tmp_path: Path) -> None:
    executor, term = _make(tmp_path, shadow=True)
    rollout = RolloutController(
        executor.state, load_rollout(ROOT / "configs" / "execution" / "rollout.yaml"),
        validated=False,
    )  # fmt: skip
    intent = _intent()
    executor.state.record_accepted(
        signal_hash=intent.signal_hash,
        intent_id=intent.intent_id,
        decision_time=intent.decision_time,
        day="d",
        dry_run=False,
        max_orders_per_day=9,
    )
    outcome = make_submit(executor, rollout)(intent, T)
    assert outcome.status == "SHADOW"
    assert term.sent == []
    assert rollout._shadow_days() == {"2026-03-04"}


def test_submit_without_an_executor_raises() -> None:
    with pytest.raises(RuntimeError, match="dry-run"):
        make_submit(None, None)(_intent(), T)


class _Recorder:
    def __init__(self) -> None:
        self.events: list[AlertEvent] = []
        self.last_error: str | None = None

    def notify(self, event: AlertEvent) -> bool:
        self.events.append(event)
        return True


def test_the_alert_hook_maps_onto_the_dispatcher(tmp_path: Path) -> None:
    recorder = _Recorder()
    alert = alert_fn(AlertDispatcher(recorder, tmp_path / "a.jsonl"), clock=lambda: T)
    alert("ROLLOUT_TIER", "info", "tier 0")
    alert("WEIRD", "loud", "unknown severity is treated as critical")
    assert [(e.code, e.severity) for e in recorder.events] == [
        ("ROLLOUT_TIER", "info"),
        ("WEIRD", "critical"),
    ]


def test_the_rollout_announcement_names_tier_action_risk_and_evidence() -> None:
    text = rollout_announcement(FUNDED_SHADOW)
    assert text is not None
    assert "tier 0 (shadow)" in text
    assert "nothing is sent" in text
    assert "UNVALIDATED" in text
    assert "h03" in text
    assert rollout_announcement(DRY) is None


def test_prop_facts_carry_every_ftmo_field(tmp_path: Path) -> None:
    state = ExecutionState(tmp_path / "s.sqlite")
    state.record_trading_day("2026-03-03")
    state.record_trading_day("2026-03-04")
    facts = PropFacts(FUNDED_SHADOW, state, PROP, requests_today=lambda: 42, request_budget=900)
    out = facts(T, _account(equity=97_000.0))
    assert out.evidence_label == "UNVALIDATED"
    assert out.strategy_id == "h03"
    assert (out.rollout_tier, out.rollout_tier_name) == (0, "shadow")
    assert out.daily_floor_distance_pct == pytest.approx(2.0)  # 97,000 vs the 95,000 floor
    assert out.max_floor_distance_pct == pytest.approx(7.0)
    assert (out.requests_today, out.request_budget) == (42, 900)
    assert out.trading_days == 2
    assert out.kill_switch_tripped is False
    state.trip_kill_switch("test")
    tripped = facts(T, None)
    assert tripped.kill_switch_tripped is True
    assert tripped.kill_switch_reason == "test"
    assert tripped.daily_floor_distance_pct is None


def test_an_empty_registry_validates_nothing(tmp_path: Path) -> None:
    spec = StrategySpec("h03", "backtest", {"a": 1})
    assert strategy_validated(ExperimentRegistry(tmp_path / "runs"), spec) is False
