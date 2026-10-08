"""The pre-registered protocol as code: alpha, pass rule, test-period lock, read-only periods."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np
import polars as pl
import pytest

from xau_edge.evaluation.periods import PERIODS
from xau_edge.evaluation.protocol import (
    FAMILY,
    evaluate,
    is_test_period_unlocked,
    required_alpha,
)
from xau_edge.evaluation.study_stats import AnalogueStatistics, analogue_statistics
from xau_edge.experiments.registry import ExperimentRegistry


def test_periods_mapping_is_read_only() -> None:
    with pytest.raises(TypeError):
        PERIODS["test"] = PERIODS["development"]  # type: ignore[index]


def test_bonferroni_alpha() -> None:
    assert required_alpha(1) == 0.05
    assert required_alpha(5) == pytest.approx(0.01)
    with pytest.raises(ValueError, match="variants"):
        required_alpha(0)


def test_smaller_alpha_widens_the_intervals() -> None:
    rng = np.random.default_rng(1)
    n = 200
    base = datetime(2026, 1, 1, tzinfo=UTC)
    study = pl.DataFrame(
        {
            "timestamp": pl.Series(
                [base + timedelta(hours=6 * i) for i in range(n)], dtype=pl.Datetime("us", "UTC")
            ),
            "analogue_mean_atr": rng.choice([-1.0, 1.0], n),
            "realized_atr": rng.normal(0, 1, n),
        }
    )
    wide = analogue_statistics(study, seed=1, n_resamples=300, alpha=0.001)
    narrow = analogue_statistics(study, seed=1, n_resamples=300, alpha=0.2)
    assert (wide.total_ci[1] - wide.total_ci[0]) > (narrow.total_ci[1] - narrow.total_ci[0])


def _stats(total_low: float, timing_low: float) -> AnalogueStatistics:
    return AnalogueStatistics(10, 0.2, (total_low, 0.3), 0.2, (timing_low, 0.3), 0.0, 0.5)


def test_pass_rule_needs_both_lower_bounds_above_zero() -> None:
    assert evaluate(_stats(0.1, 0.1))
    assert not evaluate(_stats(0.1, -0.1))
    assert not evaluate(_stats(-0.1, 0.1))
    assert not evaluate(_stats(0.0, 0.1))


def test_test_period_unlock_needs_both_earlier_periods_to_pass(tmp_path: Path) -> None:
    reg = ExperimentRegistry(tmp_path)
    params: dict[str, object] = {"window": 30}

    def rec(period: str, *, passed: bool) -> None:
        reg.record(
            family=FAMILY,
            name=period,
            dataset_ids={},
            feature_ids={},
            params=params,
            seeds={},
            period=period,
            metrics={"passed": passed},
            code_version="x",
            code_dirty=False,
        )

    assert not is_test_period_unlocked(reg, params)
    rec("development", passed=True)
    assert not is_test_period_unlocked(reg, params)
    rec("validation", passed=False)
    assert not is_test_period_unlocked(reg, params)
    rec("validation", passed=True)
    assert is_test_period_unlocked(reg, params)
    assert not is_test_period_unlocked(reg, {"window": 50})
