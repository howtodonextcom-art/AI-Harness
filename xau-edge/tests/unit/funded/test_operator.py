"""Rollout operator commands: status, promote by one with confirmation, journal and alert."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from xau_edge.execution.journal import ExecutionJournal
from xau_edge.execution.state import ExecutionState
from xau_edge.funded.operator import (
    ROLLOUT_TIER_CHANGED,
    format_report,
    promote,
    rollout_report,
)
from xau_edge.funded.rollout import RolloutController, RolloutError, load_rollout

ROOT = Path(__file__).parents[3]
NOW = datetime(2026, 3, 9, 14, 0, tzinfo=UTC)


class _Alerts:
    def __init__(self) -> None:
        self.sent: list[tuple[str, str, str]] = []

    def __call__(self, code: str, severity: str, message: str) -> None:
        self.sent.append((code, severity, message))


def _setup(
    tmp_path: Path, *, validated: bool = False
) -> tuple[RolloutController, ExecutionJournal, _Alerts]:
    config = load_rollout(ROOT / "configs" / "execution" / "rollout.yaml")
    controller = RolloutController(
        ExecutionState(tmp_path / "s.sqlite"), config, validated=validated
    )
    return controller, ExecutionJournal(tmp_path / "j.jsonl"), _Alerts()


def test_status_shows_tier_limits_evidence_and_unmet_criteria(tmp_path: Path) -> None:
    controller, _, _ = _setup(tmp_path)
    report = rollout_report(controller, NOW, evidence_label="UNVALIDATED")
    text = format_report(report)
    assert "tier in force : 0 (shadow)" in text
    assert "evidence      : UNVALIDATED" in text
    assert "NOT met for tier 1" in text
    assert "5 more trading day(s) needed" in text


def test_promote_needs_the_confirmation(tmp_path: Path) -> None:
    controller, journal, alerts = _setup(tmp_path)
    for i in range(5):
        controller.record_shadow_day(f"2026-03-0{i + 1}")
    with pytest.raises(RolloutError, match="--confirm"):
        promote(controller, journal, alerts, NOW, confirm=False, evidence_label="NONE")
    assert controller.stored_tier() == 0
    assert alerts.sent == []


def test_promote_is_refused_while_the_criteria_are_unmet_and_the_refusal_is_journalled(
    tmp_path: Path,
) -> None:
    controller, journal, alerts = _setup(tmp_path)
    with pytest.raises(RolloutError, match="refused"):
        promote(controller, journal, alerts, NOW, confirm=True, evidence_label="NONE")
    assert controller.stored_tier() == 0
    assert [e["event"] for e in journal.read()] == ["rollout.promotion_refused"]
    assert alerts.sent == []


def test_promote_moves_exactly_one_tier_journals_and_alerts(tmp_path: Path) -> None:
    controller, journal, alerts = _setup(tmp_path)
    for i in range(5):
        controller.record_shadow_day(f"2026-03-0{i + 1}")
    decision = promote(controller, journal, alerts, NOW, confirm=True, evidence_label="UNVALIDATED")
    assert decision.target == 1
    assert controller.stored_tier() == 1
    event = journal.read()[-1]
    assert event["event"] == "rollout.promoted"
    assert (event["from_tier"], event["to_tier"], event["name"]) == (0, 1, "minimum-lot")
    assert event["evidence"] == "UNVALIDATED"
    assert [a[0] for a in alerts.sent] == [ROLLOUT_TIER_CHANGED]
    assert "0 -> 1" in alerts.sent[0][2]
    # the next tier starts over: its own criteria apply, no skipping to tier 2
    with pytest.raises(RolloutError):
        promote(controller, journal, alerts, NOW, confirm=True, evidence_label="UNVALIDATED")
    assert controller.stored_tier() == 1


def test_an_unvalidated_strategy_can_never_be_promoted_past_tier_two(tmp_path: Path) -> None:
    controller, journal, alerts = _setup(tmp_path, validated=False)
    controller.state.set_meta("rollout_tier", "2")
    controller.state.set_meta("rollout_tier_started_at", (NOW - timedelta(weeks=10)).isoformat())
    report = rollout_report(controller, NOW, evidence_label="UNVALIDATED")
    assert not report.decision.eligible
    with pytest.raises(RolloutError):
        promote(controller, journal, alerts, NOW, confirm=True, evidence_label="UNVALIDATED")
    assert controller.stored_tier() == 2
