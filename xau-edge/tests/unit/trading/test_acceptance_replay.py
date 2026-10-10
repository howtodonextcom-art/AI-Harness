"""The acceptance worlds: the real desk wiring over burned bars (needs ``data/market``).

These tests are the explicit reachability proof (a real BUY and a real SELL come out of the real
label functions and the real decision, nothing is hand-built), the live-cadence parity check and the
end-to-end paper lifecycle. They skip when the burned market data is not in the checkout.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from xau_edge.trading.acceptance import SCENARIOS, AcceptanceWorld, m1_parity
from xau_edge.trading.namespace import NamespaceError, claim_root
from xau_edge.trading.paper_recovery import recover

MARKET = Path(__file__).resolve().parents[3] / "data" / "market"
pytestmark = pytest.mark.skipif(not MARKET.exists(), reason="burned market data is not here")


def tf_states(view: dict[str, Any]) -> dict[str, str]:
    return {row["timeframe"]: row["state"] for row in view["timeframes"]}


def test_a_real_buy_is_reachable_through_the_real_label_functions(tmp_path: Path) -> None:
    world = AcceptanceWorld(MARKET, tmp_path, SCENARIOS["buy_tp"])
    view = world.engine.view()
    states = tf_states(view)
    assert states["H1"] == "BULLISH"  # H1 direction
    assert states["M15"].startswith("TRIGGERED (UP")  # M15 UP structure with a pullback setup
    assert states["M5"] == "TRIGGERED (UP)"  # M5 trigger
    assert view["hero"]["state"] == "BUY_READY"
    assert view["decision"]["decision"] == "BUY"
    plan = view["trade_plan"]
    assert plan["complete"] is True
    assert plan["sl"] < plan["planned_entry"] < plan["tp1"]
    assert view["source_mode"] == "ACCEPTANCE_REPLAY"
    world.close()


def test_a_real_sell_is_reachable_through_the_real_label_functions(tmp_path: Path) -> None:
    world = AcceptanceWorld(MARKET, tmp_path, SCENARIOS["sell_ready"])
    view = world.engine.view()
    states = tf_states(view)
    assert states["H1"] == "BEARISH"
    assert states["M15"].startswith("TRIGGERED (DOWN")
    assert states["M5"] == "TRIGGERED (DOWN)"
    assert view["hero"]["state"] == "SELL_READY"
    plan = view["trade_plan"]
    assert plan["tp1"] < plan["planned_entry"] < plan["sl"]
    world.close()


@pytest.mark.parametrize(
    ("name", "state"),
    [
        ("wait", "WAIT"),
        ("market_closed", "MARKET_CLOSED"),
        ("stale", "STALE"),
        ("collector_down", "STALE"),
        ("no_spec", "UNAVAILABLE"),
        ("writer_conflict", "UNAVAILABLE"),
        ("expired", "EXPIRED_SETUP"),
    ],
)
def test_every_failure_has_its_own_hero_state_never_a_plain_wait(
    tmp_path: Path, name: str, state: str
) -> None:
    world = AcceptanceWorld(MARKET, tmp_path, SCENARIOS[name])
    assert world.engine.view()["hero"]["state"] == state
    world.close()


def test_a_corrupt_paper_state_fails_closed(tmp_path: Path) -> None:
    world = AcceptanceWorld(MARKET, tmp_path, SCENARIOS["paper_corrupt"])
    view = world.engine.view()
    assert "PAPER_STATE_ERROR" in {b["code"] for b in view["entry_blockers"]}
    assert view["desk"]["can_open"] is False
    world.close()


def test_the_closure_policy_blocks_a_new_entry_near_the_daily_close(tmp_path: Path) -> None:
    world = AcceptanceWorld(MARKET, tmp_path, SCENARIOS["buy_closure_near"])
    view = world.engine.view()
    assert view["hero"]["state"] == "BUY_READY"
    assert "CLOSURE_NEAR" in {b["code"] for b in view["entry_blockers"]}
    world.close()


def test_the_full_lifecycle_matches_the_recorded_acceptance_replay(tmp_path: Path) -> None:
    world = AcceptanceWorld(MARKET, tmp_path, SCENARIOS["buy_tp"])
    setup = world.engine.view()["decision"]["setup_id"]
    opened = world.engine.paper_open(setup_id=setup, risk_pct=0.25)
    assert opened["status"] == "OPEN"
    assert opened["source_mode"] == "ACCEPTANCE_REPLAY"
    world.advance_minutes(60)
    closed = world.engine.desk.closed_trades()
    assert len(closed) == 1
    assert closed[0]["exit_reason"] == "TAKE_PROFIT"
    assert closed[0]["r_multiple"] == pytest.approx(1.987, abs=0.01)  # PAPER_LIFECYCLE_ACCEPTANCE
    # the journal agrees with the state: a recovery dry run finds nothing to change
    report = recover(world.root, initial_capital=10_000.0, apply=False)
    assert report.ok
    assert report.differences == []
    world.close()


def test_a_replay_root_can_never_be_claimed_as_live(tmp_path: Path) -> None:
    world = AcceptanceWorld(MARKET, tmp_path, SCENARIOS["wait"])
    with pytest.raises(NamespaceError):
        claim_root(world.root, "LIVE")
    world.close()


def test_live_cadence_matches_m5_cadence_and_plain_evaluate(tmp_path: Path) -> None:
    report = m1_parity(
        MARKET,
        tmp_path,
        "1.2.1",
        datetime(2025, 12, 5, 14, 20, tzinfo=UTC),
        datetime(2025, 12, 5, 14, 55, tzinfo=UTC),
    )
    assert report.m5_compared == 7
    assert report.actionable_at_m5 >= 1  # the real BUY at 14:45 is inside the window
    assert report.mismatches == []
    assert report.duplicate_alerts == []
