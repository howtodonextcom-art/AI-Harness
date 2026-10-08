"""Staged rollout of the funded account: shadow, minimum lot, 0.25%, validated sizing (T4.3).

The tier is stored in the persistent state. ``constraints`` is what the running bot must obey at
the current tier; ``evaluate_promotion`` checks the exit criteria against the state's own records
(trading days, submission outcomes, elapsed weeks); ``promote`` moves up exactly one tier, only
when the criteria are met and only for a strategy allowed at the next tier. A strategy that is not
VALIDATED can never reach tier 3: the effective tier is capped at 2 for it, whatever is stored.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field

from xau_edge.execution.state import ExecutionState

TIER_KEY = "rollout_tier"
STARTED_KEY = "rollout_tier_started_at"
UNVALIDATED_MAX_TIER = 2
BAD_OUTCOMES = ("REJECTED", "UNKNOWN")


class ExitCriteria(BaseModel):
    """What must hold before leaving a tier."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    min_trading_days: int = 0
    min_orders: int = 0
    max_rejected_or_unknown: int | None = None
    min_weeks: float = 0.0


class TierConfig(BaseModel):
    """One tier of the rollout."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    tier: int = Field(ge=0)
    name: str
    send_orders: bool
    lot_cap: float | None = Field(default=None, gt=0)
    risk_pct: float | None = Field(default=None, gt=0, le=2.0)
    requires_validated: bool = False
    exit: ExitCriteria = Field(default_factory=ExitCriteria)


class RolloutConfig(BaseModel):
    """The ordered tiers (0..n, no gaps)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    tiers: list[TierConfig]

    def tier(self, number: int) -> TierConfig:
        """The tier with this number."""
        for t in self.tiers:
            if t.tier == number:
                return t
        msg = f"no tier {number} in the rollout configuration"
        raise KeyError(msg)

    @property
    def highest(self) -> int:
        """The last tier number."""
        return max(t.tier for t in self.tiers)


def load_rollout(path: Path | str) -> RolloutConfig:
    """Read and validate ``configs/execution/rollout.yaml``."""
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    config = RolloutConfig.model_validate(raw)
    numbers = [t.tier for t in config.tiers]
    if numbers != list(range(len(numbers))):
        msg = "rollout tiers must be numbered 0, 1, 2, ... in order"
        raise ValueError(msg)
    return config


@dataclass(frozen=True)
class TierConstraints:
    """What the bot must obey at the effective tier."""

    tier: int
    name: str
    send_orders: bool
    lot_cap: float | None
    risk_pct: float | None


@dataclass(frozen=True)
class PromotionDecision:
    """Whether the current tier's exit criteria are met."""

    current: int
    target: int | None
    eligible: bool
    unmet: tuple[str, ...]


class RolloutError(RuntimeError):
    """A promotion that is not allowed."""


class RolloutController:
    """Reads and moves the rollout tier in the persistent state."""

    def __init__(self, state: ExecutionState, config: RolloutConfig, *, validated: bool) -> None:
        self.state = state
        self.config = config
        self.validated = validated

    def stored_tier(self) -> int:
        """The tier on record (0 for a fresh state)."""
        raw = self.state.get_meta(TIER_KEY)
        if raw is None:
            return 0
        tier = int(raw)
        return min(max(tier, 0), self.config.highest)

    def effective_tier(self) -> int:
        """The tier in force: an UNVALIDATED strategy is capped at tier 2."""
        stored = self.stored_tier()
        return stored if self.validated else min(stored, UNVALIDATED_MAX_TIER)

    def constraints(self) -> TierConstraints:
        """The limits of the effective tier."""
        t = self.config.tier(self.effective_tier())
        return TierConstraints(t.tier, t.name, t.send_orders, t.lot_cap, t.risk_pct)

    def _started_at(self) -> str:
        raw = self.state.get_meta(STARTED_KEY)
        if raw is None:
            now = datetime.now(UTC).isoformat()
            self.state.set_meta(STARTED_KEY, now)
            return now
        return raw

    def evaluate_promotion(self, now: datetime) -> PromotionDecision:
        """Check the current tier's exit criteria against the state's records."""
        current = self.stored_tier()
        if current >= self.config.highest:
            return PromotionDecision(current, None, False, ("already at the highest tier",))
        target = current + 1
        unmet: list[str] = []
        next_config = self.config.tier(target)
        if next_config.requires_validated and not self.validated:
            unmet.append("tier requires a VALIDATED strategy")
        if not self.validated and target > UNVALIDATED_MAX_TIER:
            unmet.append(f"an UNVALIDATED strategy stays at tier {UNVALIDATED_MAX_TIER}")
        criteria = self.config.tier(current).exit
        started = self._started_at()
        started_dt = datetime.fromisoformat(started)
        days = [d for d in self.state.trading_days() if d >= started_dt.date().isoformat()]
        counts = self.state.submission_counts_since(started)
        orders = counts.get("FILLED", 0)
        bad = sum(counts.get(s, 0) for s in BAD_OUTCOMES)
        weeks = (now - started_dt).total_seconds() / (7 * 86400)
        counted_days = (
            len(days) if self.config.tier(current).send_orders else len(self._shadow_days())
        )
        if counted_days < criteria.min_trading_days:
            unmet.append(f"{criteria.min_trading_days - counted_days} more trading day(s) needed")
        if orders < criteria.min_orders:
            unmet.append(f"{criteria.min_orders - orders} more filled order(s) needed")
        if criteria.max_rejected_or_unknown is not None and bad > criteria.max_rejected_or_unknown:
            unmet.append(
                f"{bad} rejected/unknown order(s), at most {criteria.max_rejected_or_unknown}"
            )
        if criteria.min_weeks > 0 and weeks < criteria.min_weeks:
            unmet.append(f"{criteria.min_weeks - weeks:.1f} more week(s) needed")
        return PromotionDecision(current, target, not unmet, tuple(unmet))

    def _shadow_days(self) -> set[str]:
        """Prague days on which the shadow tier saw at least one checked order."""
        raw = self.state.get_meta("shadow_days") or ""
        return {d for d in raw.split(",") if d}

    def record_shadow_day(self, day: str) -> None:
        """Remember a day on which the shadow tier produced a checked order."""
        days = self._shadow_days() | {day}
        self.state.set_meta("shadow_days", ",".join(sorted(days)))

    def promote(self, now: datetime) -> PromotionDecision:
        """Move up one tier if (and only if) the criteria are met; raises ``RolloutError``."""
        decision = self.evaluate_promotion(now)
        if not decision.eligible or decision.target is None:
            msg = "promotion refused: " + "; ".join(decision.unmet)
            raise RolloutError(msg)
        self.state.set_meta(TIER_KEY, str(decision.target))
        self.state.set_meta(STARTED_KEY, now.isoformat())
        self.state.set_meta("shadow_days", "")
        return decision
