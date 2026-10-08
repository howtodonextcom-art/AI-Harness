"""Operator commands for the funded rollout: show the tier, promote it by exactly one (T4.3).

``scripts/rollout.py`` is a thin shell around these. There is no way to skip a tier, force a
promotion or demote through here: ``promote`` needs the explicit confirmation, re-checks the exit
criteria through ``RolloutController.promote`` (which raises unless they are met), writes the
journal and sends the ``ROLLOUT_TIER_CHANGED`` alert. The running bot reads the tier at start, so
it must be restarted to apply a promotion.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from xau_edge.execution.app import AlertFn
from xau_edge.execution.journal import ExecutionJournal
from xau_edge.funded.plan import EvidenceLabel
from xau_edge.funded.rollout import (
    PromotionDecision,
    RolloutController,
    RolloutError,
    TierConstraints,
)

ROLLOUT_TIER_CHANGED = "ROLLOUT_TIER_CHANGED"


@dataclass(frozen=True)
class RolloutReport:
    """What ``status`` shows."""

    stored_tier: int
    constraints: TierConstraints
    decision: PromotionDecision
    evidence_label: EvidenceLabel


def rollout_report(
    controller: RolloutController, now: datetime, *, evidence_label: EvidenceLabel
) -> RolloutReport:
    """The current tier, its limits and whether its exit criteria are met."""
    return RolloutReport(
        stored_tier=controller.stored_tier(),
        constraints=controller.constraints(),
        decision=controller.evaluate_promotion(now),
        evidence_label=evidence_label,
    )


def format_report(report: RolloutReport) -> str:
    """Plain text for the terminal (no account identifiers)."""
    c = report.constraints
    lines = [
        f"tier in force : {c.tier} ({c.name})",
        f"tier stored   : {report.stored_tier}",
        f"evidence      : {report.evidence_label}",
        f"sends orders  : {'yes' if c.send_orders else 'no (shadow: order_check only)'}",
        f"lot cap       : {c.lot_cap if c.lot_cap is not None else '-'}",
        f"tier risk     : {f'{c.risk_pct}%' if c.risk_pct is not None else '-'}",
    ]
    d = report.decision
    if d.target is None:
        lines.append("promotion     : none (highest tier for this strategy)")
    elif d.eligible:
        lines.append(f"promotion     : criteria MET for tier {d.target} (run: promote --confirm)")
    else:
        lines.append(f"promotion     : criteria NOT met for tier {d.target}")
    lines.extend(f"  - unmet: {u}" for u in d.unmet)
    return "\n".join(lines)


def promote(
    controller: RolloutController,
    journal: ExecutionJournal,
    alert: AlertFn,
    now: datetime,
    *,
    confirm: bool,
    evidence_label: EvidenceLabel,
) -> PromotionDecision:
    """Move up one tier when confirmed and eligible; raises ``RolloutError`` otherwise."""
    if not confirm:
        msg = "promotion needs the explicit --confirm flag"
        raise RolloutError(msg)
    before = controller.stored_tier()
    try:
        decision = controller.promote(now)
    except RolloutError as exc:
        journal.record("rollout.promotion_refused", tier=before, reason=str(exc))
        raise
    after = controller.constraints()
    journal.record(
        "rollout.promoted",
        from_tier=before,
        to_tier=decision.target,
        name=after.name,
        evidence=evidence_label,
    )
    alert(
        ROLLOUT_TIER_CHANGED,
        "warning",
        f"rollout tier {before} -> {decision.target} ({after.name}), evidence {evidence_label}; "
        "restart the bot to apply it",
    )
    return decision
