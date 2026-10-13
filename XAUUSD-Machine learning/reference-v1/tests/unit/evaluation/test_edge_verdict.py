"""Edge Program verdict and the ledger's pre-registered best-variant rule (T1.6)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from xau_edge.evaluation.edge_verdict import (
    StageResult,
    load_stage_results,
    program_verdict,
    select_best_pessimistic,
    stage_from_payload,
)


def _stage(
    variant: str,
    period: str,
    trades: int,
    pess: float,
    *,
    passed: bool = False,
    at: str = "2026-10-08T14:00:00+00:00",
) -> StageResult:
    return StageResult(variant, period, at, "id", trades, pess + 0.01, pess, passed, ())


def _payload(status: str = "completed") -> dict[str, Any]:
    return {
        "variant": "H03-c1.0",
        "period": {"name": "val"},
        "recorded_at": "2026-10-08T14:51:42+00:00",
        "registry_id": "aa83",
        "status": status,
        "stage_pass": False,
        "scenarios": {
            "base": {
                "trades": 119,
                "mean_net_r": -0.05,
                "verdict": {"min_trades": {"passed": True}, "profit_factor": {"passed": False}},
            },
            "pessimistic": {"trades": 119, "mean_net_r": -0.06},
        },
    }


def test_a_payload_reduces_to_its_stage_and_incomplete_runs_are_ignored(tmp_path: Path) -> None:
    stage = stage_from_payload(_payload())
    assert stage is not None
    assert stage.trades == 119
    assert stage.pessimistic_mean_net_r == -0.06
    assert stage.failed_criteria == ("profit_factor",)
    assert stage_from_payload(_payload("started")) is None
    (tmp_path / "H03-c1.0_val_aa83.json").write_text(json.dumps(_payload()), encoding="utf-8")
    (tmp_path / "H03-c1.0_test_bb.json").write_text(
        json.dumps(_payload("started")), encoding="utf-8"
    )
    assert [s.period for s in load_stage_results(tmp_path)] == ["val"]


def test_best_is_the_maximin_of_pessimistic_means_with_100_trades_in_both_periods() -> None:
    results = [
        _stage("H01-a", "dev", 500, -0.09),
        _stage("H01-a", "val", 400, -0.03),
        _stage("H02-b", "dev", 300, -0.01),
        _stage("H02-b", "val", 150, -0.07),
        _stage("H03-c", "dev", 300, 0.20),  # best numbers but too few trades on val
        _stage("H03-c", "val", 99, 0.30),
    ]
    best = select_best_pessimistic(results)
    assert best.variant == "H02-b"
    assert best.score == -0.07
    assert best.positive is False
    assert best.eligible == ("H01-a", "H02-b")


def test_the_latest_completed_record_decides_and_a_positive_best_is_flagged() -> None:
    results = [
        _stage("H01-a", "dev", 200, -0.5, at="2026-10-08T10:00:00+00:00"),
        _stage("H01-a", "dev", 200, 0.02, at="2026-10-08T11:00:00+00:00"),
        _stage("H01-a", "val", 200, 0.05),
    ]
    best = select_best_pessimistic(results)
    assert best.variant == "H01-a"
    assert best.score == 0.02
    assert best.positive is True


def test_no_eligible_variant_gives_no_choice() -> None:
    best = select_best_pessimistic([_stage("H01-a", "dev", 10, 0.1)])
    assert best.variant is None
    assert best.positive is False


def test_the_verdict_is_b_unless_a_test_stage_passed() -> None:
    results = [_stage("H01-a", "dev", 200, 0.1, passed=True), _stage("H01-a", "val", 200, 0.1)]
    assert program_verdict(results) == "B"
    assert program_verdict([*results, _stage("H01-a", "test", 200, 0.1, passed=True)]) == "A"
