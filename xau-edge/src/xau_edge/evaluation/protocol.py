"""Executable form of the pre-registered protocol in docs/evals/edge-criteria.md."""

from __future__ import annotations

from typing import Any

from xau_edge.evaluation.study_stats import AnalogueStatistics
from xau_edge.experiments.registry import ExperimentRegistry

FAMILY = "analogue-study"


def required_alpha(variants: int, base: float = 0.05) -> float:
    """Two-sided significance level after counting ``variants`` tried (Bonferroni)."""
    if variants < 1:
        msg = f"variants must be >= 1, got {variants}"
        raise ValueError(msg)
    return base / variants


def evaluate(stats: AnalogueStatistics) -> bool:
    """Pass rule: the lower bounds of BOTH intervals are above zero."""
    return stats.total_ci[0] > 0 and stats.timing_ci[0] > 0


def is_test_period_unlocked(registry: ExperimentRegistry, params: dict[str, Any]) -> bool:
    """True only if development AND validation records with these params both passed."""
    passed = {
        rec.period
        for rec in registry.list(FAMILY)
        if rec.params == params and rec.metrics.get("passed") is True
    }
    return {"development", "validation"} <= passed
