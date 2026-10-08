"""Status snapshot: the FTMO-facing facts and the funded mode (ADR-0020, T4.5)."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from xau_edge.execution.reconcile import BrokerAccount, BrokerSnapshot
from xau_edge.execution.status import (
    StatusPropFacts,
    build_status,
    evaluate_health,
    read_status,
    write_status,
)

NOW = datetime(2026, 10, 8, 12, 0, tzinfo=UTC)


def _snapshot(*, demo: bool) -> BrokerSnapshot:
    account = BrokerAccount(account_id="900001", is_demo=demo, balance=1.0, equity=1.0)
    return BrokerSnapshot(account=account, positions=(), closed=(), taken_at=NOW)


def test_an_old_status_without_prop_facts_still_reads(tmp_path: Path) -> None:
    status = build_status(
        NOW, mode="dry-run", symbol="XAUUSD", snapshot=None, reconcile=None, report=None
    )
    assert status.prop == StatusPropFacts()
    path = tmp_path / "status.json"
    write_status(path, status)
    assert read_status(path) == status


def test_prop_facts_round_trip_and_carry_the_unvalidated_label(tmp_path: Path) -> None:
    facts = StatusPropFacts(
        evidence_label="UNVALIDATED",
        strategy_id="h03-c0.9",
        rollout_tier=0,
        rollout_tier_name="shadow",
        daily_floor_distance_pct=4.2,
        max_floor_distance_pct=9.1,
        requests_today=37,
        request_budget=1000,
        trading_days=2,
        kill_switch_tripped=False,
        kill_switch_reason="",
    )
    status = build_status(
        NOW,
        mode="funded",
        symbol="XAUUSD",
        snapshot=_snapshot(demo=False),
        reconcile=None,
        report=None,
        prop=facts,
    )
    path = tmp_path / "status.json"
    write_status(path, status)
    loaded = read_status(path)
    assert loaded is not None
    assert loaded.mode == "funded"
    assert loaded.prop.evidence_label == "UNVALIDATED"
    assert loaded.live_trading is False


def test_a_non_demo_account_alerts_except_in_funded_mode() -> None:
    demo_mode = build_status(
        NOW, mode="demo", symbol="XAUUSD", snapshot=_snapshot(demo=False), reconcile=None,
        report=None,
    )  # fmt: skip
    funded = build_status(
        NOW, mode="funded", symbol="XAUUSD", snapshot=_snapshot(demo=False), reconcile=None,
        report=None,
    )  # fmt: skip
    assert "ACCOUNT_NOT_DEMO" in {a.code for a in evaluate_health(demo_mode, None, NOW)}
    assert "ACCOUNT_NOT_DEMO" not in {a.code for a in evaluate_health(funded, None, NOW)}
