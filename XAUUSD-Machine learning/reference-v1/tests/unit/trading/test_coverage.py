"""Decision-telemetry coverage: expected = closed M1 bars the engine could decide on."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from xau_edge.trading.coverage import (
    COVERAGE_OK_PCT,
    apply_to_forward,
    decision_coverage,
)

T0 = datetime(2026, 10, 9, 13, 0, tzinfo=UTC)


def bars(n: int, skip: set[int] | None = None) -> list[datetime]:
    return [T0 + timedelta(minutes=i) for i in range(n) if i not in (skip or set())]


def row(i: int, *, delay: float = 5.0, exact: bool = True, run: str = "r1") -> dict[str, Any]:
    bar = T0 + timedelta(minutes=i)
    at = bar + timedelta(minutes=1, seconds=delay)
    out: dict[str, Any] = {"at": at.isoformat(), "run": run}
    if exact:
        out["m1_bar"] = bar.isoformat()
    return out


def cover(expected: list[datetime], rows: list[dict[str, Any]], n: int = 100) -> dict[str, Any]:
    return decision_coverage(expected, rows, window_from=T0, window_to=T0 + timedelta(minutes=n))


def test_every_expected_bar_recorded_is_full_coverage() -> None:
    result = cover(bars(60), [row(i) for i in range(60)])
    assert (result["expected_m1_decisions"], result["recorded_m1_decisions"]) == (60, 60)
    assert result["coverage_pct"] == 100.0 and result["missing"] == 0 and result["complete"]
    assert result["missing_intervals"] == [] and result["duplicate_rows"] == 0


def test_a_restart_is_a_merged_missing_interval_not_a_pile_of_minutes() -> None:
    rows = [row(i) for i in range(10)] + [row(i, run="r2") for i in range(40, 60)]
    result = cover(bars(60), rows)
    assert result["recorded_m1_decisions"] == 30 and result["missing"] == 30
    assert result["coverage_pct"] == 50.0 and not result["complete"]
    only = result["missing_intervals"]
    assert len(only) == 1 and only[0]["minutes"] == 30
    assert only[0]["from"] == (T0 + timedelta(minutes=10)).isoformat()
    assert only[0]["to"] == (T0 + timedelta(minutes=39)).isoformat()


def test_bars_the_collector_never_delivered_are_not_expected() -> None:
    # no ledger bars for minutes 20..29 (market closed or collector down): nothing to decide on
    result = cover(
        bars(60, skip=set(range(20, 30))), [row(i) for i in range(60) if not 20 <= i < 30]
    )
    assert result["expected_m1_decisions"] == 50 and result["coverage_pct"] == 100.0


def test_duplicates_late_and_outside_rows_are_counted_separately() -> None:
    rows = [row(i) for i in range(5)] + [row(2), row(3, delay=200.0), row(500)]
    result = cover(bars(5), rows, n=600)
    assert result["recorded_m1_decisions"] == 5
    assert result["duplicate_rows"] == 2  # bars 2 and 3 were written twice
    assert result["late_rows"] == 1  # 200 s after the bar closed
    assert result["outside_expected_rows"] == 1  # bar 500 is not an expected bar


def test_rows_without_m1_bar_are_mapped_by_wall_clock_and_flagged_approximate() -> None:
    result = cover(bars(10), [row(i, exact=False) for i in range(10)])
    assert result["recorded_m1_decisions"] == 10 and result["approx_rows"] == 10
    assert result["late_rows"] == 0  # lateness is only judged on exact rows


def test_an_empty_window_is_not_complete() -> None:
    result = cover([], [])
    assert result["expected_m1_decisions"] == 0 and not result["complete"]


def test_incomplete_coverage_turns_a_plain_f0_into_forward_evidence_incomplete() -> None:
    forward = {
        "level": "F0",
        "text": "no live actionable setup observed yet",
        "live": True,
        "counts": {},
    }
    bad = cover(bars(60), [row(i) for i in range(20)])
    out = apply_to_forward(forward, bad)
    assert out["level"] == "F0" and out["evidence_complete"] is False
    assert out["text"].startswith("FORWARD EVIDENCE INCOMPLETE: only 33.3%")
    good = apply_to_forward(forward, cover(bars(60), [row(i) for i in range(60)]))
    assert good["evidence_complete"] is True and good["text"] == forward["text"]
    # a replay never carries live evidence, so coverage does not touch it
    replay = {"level": "F0", "text": "replay", "live": False, "counts": {}}
    assert apply_to_forward(replay, bad) == {
        **replay,
        "evidence_complete": None,
        "coverage_pct": None,
    }
    assert COVERAGE_OK_PCT == 95.0
