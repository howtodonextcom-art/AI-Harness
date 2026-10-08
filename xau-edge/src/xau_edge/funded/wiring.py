"""From a ``RunPlan`` to the bot's collaborators: limits, safety, executor settings, hooks.

Everything here is built from the plan and passed-in objects; nothing opens a terminal. The script
``scripts/demo_trader.py`` only composes these, so the rules about what each mode may do live in
tested code:

* the risk engine sizes with the plan's per-trade risk and never above the plan's lot limit;
* ``ExecutionSafety`` checks the REAL environment and account (not the ``paper`` default, d5);
* the executor exists only when the plan sends or shadows, and its lot limit is the tier's cap;
* a SHADOW result counts the Prague day toward the shadow tier's exit criteria;
* ``status.json`` carries the FTMO-facing facts of every cycle.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import get_args

from xau_edge.brokers.mt5_demo.executor import ExecutorConfig, Mt5DemoExecutor
from xau_edge.execution.app import AlertFn
from xau_edge.execution.guards import PRAGUE, evaluate_flatten
from xau_edge.execution.order_intent import OrderIntent
from xau_edge.execution.runner import SubmitOutcome
from xau_edge.execution.safety import ExecutionSafety, day_key
from xau_edge.execution.state import ExecutionState
from xau_edge.execution.status import Severity, StatusPropFacts
from xau_edge.experiments.registry import ExperimentRegistry
from xau_edge.funded.plan import RunPlan
from xau_edge.funded.rollout import RolloutController
from xau_edge.ops.notifier import AlertDispatcher, AlertEvent
from xau_edge.risk.engine import AccountState, RiskLimits
from xau_edge.risk.prop_rules import PropProfile
from xau_edge.signals.evidence import evidence_for_strategy
from xau_edge.signals.schema import EvidenceStatus
from xau_edge.signals.strategy_registry import StrategySpec

_SEVERITIES: frozenset[str] = frozenset(get_args(Severity))


def risk_limits(plan: RunPlan) -> RiskLimits:
    """Trade limits with the plan's per-trade risk; lots never above the plan's maximum."""
    return RiskLimits(
        risk_per_trade_pct=plan.risk_pct, max_lot=plan.max_lots, max_total_lots=plan.max_lots
    )


def execution_safety(
    plan: RunPlan, *, account: str, symbols: tuple[str, ...], max_orders_per_day: int
) -> ExecutionSafety:
    """Safety limits for the real environment and the logged-in account (blocker d5, T2.11)."""
    return ExecutionSafety(
        environment=plan.status_mode,
        allowed_environments=(plan.status_mode,),
        allowed_accounts=plan.allowed_accounts,
        allowed_symbols=symbols,
        max_lots=plan.max_lots,
        max_orders_per_day=max_orders_per_day,
        dry_run=plan.bridge_dry_run,
        account=account,
    )


def executor_config(
    plan: RunPlan, *, symbols: tuple[str, ...], deviation_points: int
) -> ExecutorConfig | None:
    """The executor's settings, or ``None`` when the plan neither sends nor shadows."""
    if not plan.uses_executor:
        return None
    max_lots = min(plan.max_lots, plan.lot_cap) if plan.lot_cap is not None else plan.max_lots
    return ExecutorConfig(
        enabled=True,
        dry_run=False,
        allowed_accounts=plan.allowed_accounts,
        symbols=symbols,
        magic=plan.magic,
        max_lots=max_lots,
        deviation_points=deviation_points,
        shadow=plan.shadow,
    )


def make_submit(
    executor: Mt5DemoExecutor | None, rollout: RolloutController | None
) -> Callable[[OrderIntent, datetime], SubmitOutcome]:
    """The cycle's submit function; a SHADOW answer records the Prague day for the rollout."""

    def submit(intent: OrderIntent, at: datetime) -> SubmitOutcome:
        if executor is None:
            msg = "no executor in dry-run mode"
            raise RuntimeError(msg)
        outcome = executor.submit(intent, at)
        if outcome.status == "SHADOW" and rollout is not None:
            rollout.record_shadow_day(day_key(at.astimezone(PRAGUE).date()))
        return SubmitOutcome(outcome.status, outcome.ticket)

    return submit


def alert_fn(
    dispatcher: AlertDispatcher, clock: Callable[[], datetime] = lambda: datetime.now(UTC)
) -> AlertFn:
    """``BotApp``'s ``alert(code, severity, message)`` on top of the dispatcher (never raises)."""

    def alert(code: str, severity: str, message: str) -> None:
        level: Severity = severity if severity in _SEVERITIES else "critical"  # type: ignore[assignment]
        dispatcher.dispatch(AlertEvent(code=code, severity=level, message=message, at=clock()))

    return alert


def strategy_validated(registry: ExperimentRegistry, spec: StrategySpec) -> bool:
    """True when the evidence gate holds a VALIDATED record for exactly this strategy."""
    return evidence_for_strategy(registry, spec) is EvidenceStatus.VALIDATED


def rollout_announcement(plan: RunPlan) -> str | None:
    """The start-up ``ROLLOUT_TIER`` message for a funded plan, ``None`` otherwise."""
    if plan.rollout_tier is None:
        return None
    action = "sends orders" if plan.send_orders else "shadow: order_check only, nothing is sent"
    cap = f", lot cap {plan.lot_cap}" if plan.lot_cap is not None else ""
    return (
        f"rollout tier {plan.rollout_tier} ({plan.rollout_tier_name}): {action}; "
        f"risk {plan.risk_pct}%/trade{cap}; evidence {plan.evidence_label}"
        + (f" strategy {plan.strategy_id}" if plan.strategy_id else "")
    )


@dataclass(frozen=True)
class PropFacts:
    """``BotApp``'s ``prop_facts`` hook: the FTMO-facing facts for ``status.json``."""

    plan: RunPlan
    state: ExecutionState
    prop: PropProfile
    requests_today: Callable[[], int]
    request_budget: int
    flatten_distance_pct: float = 1.0

    def __call__(self, now: datetime, account: AccountState | None) -> StatusPropFacts:
        tripped, reason = self.state.kill_switch_state()
        daily = maximum = None
        if account is not None:
            decision = evaluate_flatten(account, self.prop, distance_pct=self.flatten_distance_pct)
            daily, maximum = decision.daily_distance_pct, decision.max_distance_pct
        return StatusPropFacts(
            evidence_label=self.plan.evidence_label,
            strategy_id=self.plan.strategy_id,
            rollout_tier=self.plan.rollout_tier,
            rollout_tier_name=self.plan.rollout_tier_name,
            daily_floor_distance_pct=daily,
            max_floor_distance_pct=maximum,
            requests_today=self.requests_today(),
            request_budget=self.request_budget,
            trading_days=len(self.state.trading_days()),
            kill_switch_tripped=tripped,
            kill_switch_reason=reason or None,
        )
