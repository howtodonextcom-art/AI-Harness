"""What this process may do, decided once at start-up, as a frozen value (ADR-0020, T4.6).

``build_run_plan`` is a pure function: settings, the account the terminal reports, the funded rules
file, the rollout tier in force, whether the strategy is VALIDATED and the ``--confirm-mode`` flag
go in; a ``RunPlan`` comes out, or an exception and nothing may run. It always goes through
``authorize_start`` (whitelists, server, ``must_verify`` rules, confirmation) first.

Rules it enforces on top:

* DRY_RUN never sends and never shadows; DEMO sends; FUNDED follows the rollout tier.
* Tier 0 (shadow): the executor runs every gate and the broker's ``order_check`` but never sends.
* Tier 1: the tier's lot cap. Tier 2: the tier's risk. Tier 3: VALIDATED only, with
  ``funded_validated_risk_pct`` (refused if missing).
* Anything not VALIDATED risks at most ``min(tier risk, funded_risk_pct, 0.25)`` per trade, whatever
  the configuration or the tier file says.
* The owner override (D2) exists only in FUNDED and only with
  ``XAU_EDGE_FUNDED_ALLOW_UNVALIDATED=true`` plus ``XAU_EDGE_FUNDED_STRATEGY_ID``. Without a
  VALIDATED strategy and without the override, funded still runs but the evidence gate keeps every
  signal at WAIT.
* The reader and reconciler require a DEMO ``trade_mode`` except in FUNDED, where the account is
  identified by whitelist and server instead (FTMO may report either trade mode).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from xau_edge.config import Settings
from xau_edge.execution.override import OverridePolicy
from xau_edge.funded.identity import AccountIdentity, ModeError, RunMode
from xau_edge.funded.rollout import UNVALIDATED_MAX_TIER, TierConstraints
from xau_edge.funded.rules import FundedRules
from xau_edge.funded.startup import authorize_start
from xau_edge.risk.engine import RiskLimits

UNVALIDATED_RISK_CAP_PCT = 0.25
"""Hard per-trade ceiling for anything that is not VALIDATED (decision D2); not configurable."""

EvidenceLabel = Literal["VALIDATED", "UNVALIDATED", "NONE"]
StatusMode = Literal["dry-run", "demo", "funded"]

_STATUS_MODE: dict[RunMode, StatusMode] = {
    RunMode.DRY_RUN: "dry-run",
    RunMode.DEMO: "demo",
    RunMode.FUNDED: "funded",
}


class PlanError(ModeError):
    """The combination of mode, tier and evidence is not allowed; nothing may run."""


@dataclass(frozen=True)
class RunPlan:
    """Everything the start-up decided; the script wires collaborators from it and nothing else."""

    mode: RunMode
    magic: int | None
    allowed_accounts: tuple[str, ...]
    initial_capital: float | None
    prop_profile_source: str
    state_path: Path
    journal_path: Path
    send_orders: bool
    shadow: bool
    lot_cap: float | None
    max_lots: float
    risk_pct: float
    override: OverridePolicy | None
    strategy_id: str | None
    evidence_label: EvidenceLabel
    require_demo: bool
    rollout_tier: int | None = None
    rollout_tier_name: str | None = None

    @property
    def status_mode(self) -> StatusMode:
        """The mode as written to ``status.json``."""
        return _STATUS_MODE[self.mode]

    @property
    def uses_executor(self) -> bool:
        """True when intents reach the broker adapter (to be sent, or only checked in shadow)."""
        return self.send_orders or self.shadow

    @property
    def bridge_dry_run(self) -> bool:
        """The bridge produces dry-run intents unless an executor will take them."""
        return not self.uses_executor


def _csv(value: str) -> tuple[str, ...]:
    return tuple(sorted({item.strip() for item in value.split(",") if item.strip()}))


def override_enabled(settings: Settings, *, validated: bool) -> bool:
    """D2 applies: funded mode, the owner's flag, a named strategy, and no VALIDATED strategy."""
    return (
        settings.enable_funded_trading
        and not validated
        and settings.funded_allow_unvalidated
        and bool(settings.funded_strategy_id.strip())
    )


def evidence_label(settings: Settings, *, validated: bool) -> EvidenceLabel:
    """VALIDATED, UNVALIDATED (owner override in force) or NONE (every signal stays WAIT)."""
    if validated:
        return "VALIDATED"
    return "UNVALIDATED" if override_enabled(settings, validated=validated) else "NONE"


def _funded_risk(settings: Settings, tier: TierConstraints, *, validated: bool) -> float:
    """Per-trade risk in percent for the funded account at ``tier``."""
    if tier.tier > UNVALIDATED_MAX_TIER:
        if not validated:
            msg = f"tier {tier.tier} is for VALIDATED strategies only"
            raise PlanError(msg)
        if settings.funded_validated_risk_pct is None:
            msg = (
                f"tier {tier.tier} needs XAU_EDGE_FUNDED_VALIDATED_RISK_PCT "
                "(the Monte Carlo prop filter result)"
            )
            raise PlanError(msg)
        return settings.funded_validated_risk_pct
    ceiling = min(settings.funded_risk_pct, UNVALIDATED_RISK_CAP_PCT)
    return min(tier.risk_pct, ceiling) if tier.risk_pct is not None else ceiling


def build_run_plan(
    settings: Settings,
    identity: AccountIdentity,
    *,
    rules: FundedRules | None,
    tier: TierConstraints | None,
    validated: bool,
    confirm: str | None,
    demo_prop_source: str = "configs/prop/ftmo_2step.yaml",
) -> RunPlan:
    """The plan for this process, or ``ModeError``/``FundedRulesNotVerifiedError``/``PlanError``."""
    mode = authorize_start(settings, identity, confirm=confirm, rules=rules)
    if mode is not RunMode.FUNDED:
        demo = mode is RunMode.DEMO
        return RunPlan(
            mode=mode,
            magic=settings.demo_magic,
            allowed_accounts=_csv(settings.demo_allowed_accounts) if demo else (identity.login,),
            initial_capital=settings.demo_initial_capital,
            prop_profile_source=demo_prop_source,
            state_path=settings.demo_state_path,
            journal_path=settings.demo_journal_path,
            send_orders=demo,
            shadow=False,
            lot_cap=None,
            max_lots=settings.demo_max_lots,
            risk_pct=RiskLimits().risk_per_trade_pct,
            override=None,
            strategy_id=None,
            evidence_label="VALIDATED" if validated else "NONE",
            require_demo=True,
        )
    if tier is None:
        msg = "funded mode needs the rollout tier (configs/execution/rollout.yaml)"
        raise PlanError(msg)
    strategy_id = settings.funded_strategy_id.strip()
    override_on = override_enabled(settings, validated=validated)
    risk_pct = _funded_risk(settings, tier, validated=validated)
    if not validated and risk_pct > UNVALIDATED_RISK_CAP_PCT:  # defence in depth
        msg = f"an UNVALIDATED risk of {risk_pct}% is above the {UNVALIDATED_RISK_CAP_PCT}% cap"
        raise PlanError(msg)
    return RunPlan(
        mode=mode,
        magic=settings.funded_magic,
        allowed_accounts=_csv(settings.funded_allowed_accounts),
        initial_capital=settings.funded_initial_capital,
        prop_profile_source=str(settings.funded_profile_path),
        state_path=settings.funded_state_path,
        journal_path=settings.funded_journal_path,
        send_orders=tier.send_orders,
        shadow=not tier.send_orders,
        lot_cap=tier.lot_cap,
        max_lots=settings.funded_max_lots,
        risk_pct=risk_pct,
        override=OverridePolicy(enabled=True, strategy_id=strategy_id) if override_on else None,
        strategy_id=strategy_id or None,
        evidence_label=evidence_label(settings, validated=validated),
        require_demo=False,
        rollout_tier=tier.tier,
        rollout_tier_name=tier.name,
    )
