"""Edge-decay rules (roadmap section 23.4): a SUGGESTION of a lower state from forward trades.

The thresholds live in ``configs/research/decay.yaml`` (committed before use). The result is advice
shown in the console: the state itself changes only through the demote command, and never upward.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field


class DecayConfig(BaseModel):
    """Fixed thresholds."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    window_trades: int = Field(default=60, ge=10)
    watch_windows_for_degraded: int = Field(default=2, ge=1)
    cost_drift_degraded: float = Field(default=1.5, gt=1.0)
    drawdown_multiple_disabled: float = Field(default=1.5, gt=1.0)
    min_trades_for_conclusion: int = Field(default=100, ge=1)


def load_decay_config(path: Path | str) -> DecayConfig:
    """Read ``configs/research/decay.yaml``."""
    return DecayConfig.model_validate(yaml.safe_load(Path(path).read_text(encoding="utf-8")))


@dataclass(frozen=True)
class DecayResult:
    """The suggested state and why."""

    suggestion: str
    reasons: tuple[str, ...]
    window_means: tuple[float, ...]
    max_drawdown_r: float


def max_drawdown_r(net_r: list[float]) -> float:
    """Largest peak-to-trough fall of the cumulative R curve."""
    peak = cum = worst = 0.0
    for value in net_r:
        cum += value
        peak = max(peak, cum)
        worst = max(worst, peak - cum)
    return worst


def evaluate_decay(
    net_r: list[float],
    *,
    ci_lower: float,
    validated_max_dd_r: float,
    cost_drift: float,
    config: DecayConfig,
) -> DecayResult:
    """Suggest VALIDATED, WATCH, DEGRADED or DISABLED. Too few trades: no suggestion change."""
    if any(not math.isfinite(v) for v in net_r) or not math.isfinite(cost_drift):
        return DecayResult("UNKNOWN", ("non-finite input",), (), 0.0)
    dd = max_drawdown_r(net_r)
    size = config.window_trades
    windows = [net_r[i : i + size] for i in range(len(net_r) - size, -1, -size) if i >= 0]
    means = tuple(sum(w) / len(w) for w in windows if len(w) == size)  # newest first
    reasons: list[str] = []
    if dd > config.drawdown_multiple_disabled * validated_max_dd_r:
        reasons.append("drawdown above 1.5x the validated one")
        return DecayResult("DISABLED", tuple(reasons), means, dd)
    if cost_drift > config.cost_drift_degraded:
        reasons.append("cost drift above the limit")
        return DecayResult("DEGRADED", tuple(reasons), means, dd)
    needed = config.watch_windows_for_degraded
    below = [m < ci_lower for m in means]
    if len(below) >= needed and all(below[:needed]):
        reasons.append(f"{needed} consecutive windows below the validated lower bound")
        return DecayResult("DEGRADED", tuple(reasons), means, dd)
    if below and below[0]:
        reasons.append("latest window below the validated lower bound")
        return DecayResult("WATCH", tuple(reasons), means, dd)
    return DecayResult("VALIDATED", tuple(reasons), means, dd)
