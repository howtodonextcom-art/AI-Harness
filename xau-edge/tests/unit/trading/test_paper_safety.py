"""Paper desk safety: fail closed, crash windows, journal recovery, read-only, closure policy."""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from tests.unit.trading.helpers import SPEC
from tests.unit.trading.test_paper_desk import NOW, Q, bars, buy, make_desk, opened
from xau_edge.trading.paper_desk import (
    CLOSURE_NEAR,
    STATE_ERROR,
    WRITER_ERROR,
    ClosurePolicy,
    DeskExit,
    DeskRefusal,
    PaperDesk,
    PaperStatus,
)
from xau_edge.trading.paper_recovery import recover, replay_journal


class Crash(BaseException):
    """An injected process death; a BaseException, so no ``except Exception`` can hide it."""


def journal_events(root: Path) -> list[str]:
    path = root / "paper_journal.jsonl"
    return [json.loads(x)["event"] for x in path.read_text(encoding="utf-8").splitlines() if x]


# -- fail closed -----------------------------------------------------------------------------------


def test_a_corrupt_state_blocks_every_new_entry_and_every_change(tmp_path: Path) -> None:
    desk = make_desk(tmp_path)
    rec = opened(desk)
    (tmp_path / "paper_desk.json").write_text("{not json", encoding="utf-8")
    broken = make_desk(tmp_path)
    assert broken.fault is not None and broken.fault[0] == STATE_ERROR
    assert STATE_ERROR in broken.can_open(NOW, "LONDON", 0.25, Q())
    with pytest.raises(DeskRefusal) as info:
        broken.open_from_decision(
            buy(), risk_pct=0.25, quote=Q(), spec=SPEC, now=NOW + timedelta(minutes=9)
        )
    assert info.value.code == STATE_ERROR
    with pytest.raises(DeskRefusal) as closing:
        broken.manual_close(rec["trade_id"], Q(), NOW)
    assert closing.value.code == STATE_ERROR
    before = (tmp_path / "paper_journal.jsonl").read_text(encoding="utf-8")
    assert broken.process_bars(bars([(1, 2000.0, 2001.0, 1990.0, 1995.0)])) == []
    assert (tmp_path / "paper_journal.jsonl").read_text(
        encoding="utf-8"
    ) == before  # nothing written


def test_a_read_only_desk_never_writes_and_says_why(tmp_path: Path) -> None:
    desk = make_desk(tmp_path)
    opened(desk)
    ro = PaperDesk(tmp_path, clock=lambda: NOW, writable=False)
    assert ro.fault is not None and ro.fault[0] == WRITER_ERROR
    with pytest.raises(DeskRefusal) as info:
        ro.open_from_decision(buy(), risk_pct=0.25, quote=Q(), spec=SPEC, now=NOW)
    assert info.value.code == WRITER_ERROR
    with pytest.raises(DeskRefusal):
        ro.manual_close("T00001", Q(), NOW)
    assert ro.open_trade() is not None  # it can still READ the open trade


# -- crash windows ---------------------------------------------------------------------------------


def test_a_crash_before_the_fill_leaves_no_ghost_and_the_setup_stays_consumed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    desk = make_desk(tmp_path)

    def die(_order: object) -> object:
        raise Crash

    monkeypatch.setattr(desk.broker, "submit_order", die)
    signal = buy()
    with pytest.raises(Crash):
        desk.open_from_decision(signal, risk_pct=0.25, quote=Q(), spec=SPEC, now=NOW)
    assert journal_events(tmp_path) == ["paper.pending"]  # the intent is on disk, the fill is not
    restarted = make_desk(tmp_path)
    assert restarted.fault is None and restarted.open_trade() is None
    assert restarted.recovered_orphans == ["T00001"]
    assert journal_events(tmp_path) == ["paper.pending", "paper.abort"]
    assert restarted.broker.get_account().open_positions == 0
    with pytest.raises(DeskRefusal) as again:  # the same setup can never become a second order
        restarted.open_from_decision(signal, risk_pct=0.25, quote=Q(), spec=SPEC, now=NOW)
    assert again.value.code == "DUPLICATE_SETUP"


def test_a_crash_after_the_fill_but_before_the_commit_is_also_an_orphan(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    desk = make_desk(tmp_path)
    real = desk._journal

    def journal(event: str, record: dict[str, Any]) -> None:
        if event == "paper.open":
            raise Crash
        real(event, record)

    monkeypatch.setattr(desk, "_journal", journal)
    with pytest.raises(Crash):
        desk.open_from_decision(buy(), risk_pct=0.25, quote=Q(), spec=SPEC, now=NOW)
    restarted = make_desk(tmp_path)
    assert (
        restarted.fault is None and restarted.open_trade() is None
    )  # the memory-only fill is gone
    assert restarted.recovered_orphans == ["T00001"]


def test_a_crash_after_the_commit_before_the_snapshot_fails_closed_then_recovers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    desk = make_desk(tmp_path)

    def die() -> None:
        raise Crash

    monkeypatch.setattr(desk, "_save", die)
    with pytest.raises(Crash):
        desk.open_from_decision(buy(), risk_pct=0.25, quote=Q(), spec=SPEC, now=NOW)
    assert "paper.open" in journal_events(tmp_path)  # committed
    restarted = make_desk(tmp_path)
    assert restarted.fault is not None and restarted.fault[0] == STATE_ERROR  # fail closed
    assert "journal" in (restarted.integrity_error or "")
    dry = recover(tmp_path, initial_capital=restarted.config.capital, apply=False)
    assert not dry.ok and dry.differences and not dry.applied
    assert not (tmp_path / "paper_desk.json").exists()  # a dry run touches nothing
    done = recover(tmp_path, initial_capital=restarted.config.capital, apply=True, now=NOW)
    assert done.applied
    healed = make_desk(tmp_path)
    assert healed.fault is None
    trade = healed.open_trade()
    assert trade is not None and trade["status"] == PaperStatus.OPEN
    assert healed.broker.get_account().open_positions == 1  # the position was rebuilt, once
    # and the rebuilt desk keeps managing it: a stop-out closes it
    stopped = healed.process_bars(bars([(1, 2000.0, 2000.2, trade["sl"] - 1, trade["sl"])]))
    assert len(stopped) == 1 and stopped[0]["exit_reason"] == "STOP_LOSS"


def test_a_crash_between_the_close_commit_and_the_snapshot_recovers_the_closed_trade(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    desk = make_desk(tmp_path)
    rec = opened(desk)
    calls = {"n": 0}
    real_save = desk._save

    def flaky() -> None:
        calls["n"] += 1
        raise Crash

    monkeypatch.setattr(desk, "_save", flaky)
    with pytest.raises(Crash):
        desk.manual_close(rec["trade_id"], Q(bid=2000.6, ask=2000.85), NOW + timedelta(minutes=2))
    monkeypatch.setattr(desk, "_save", real_save)
    restarted = make_desk(tmp_path)
    assert restarted.fault is not None  # the snapshot still says OPEN, the journal says CLOSED
    assert any("OPEN" in d and "CLOSED" in d for d in [restarted.integrity_error or ""])
    recover(tmp_path, initial_capital=restarted.config.capital, apply=True, now=NOW)
    healed = make_desk(tmp_path)
    assert healed.fault is None and healed.open_trade() is None
    closed = healed.closed_trades()
    assert len(closed) == 1 and closed[0]["exit_reason"] == DeskExit.MANUAL_CLOSE.value
    assert healed.broker.get_account().balance == pytest.approx(10_000.0 + closed[0]["net_pnl"])


def test_a_state_that_agrees_with_its_journal_has_no_fault_and_a_recovery_dry_run_is_clean(
    tmp_path: Path,
) -> None:
    desk = make_desk(tmp_path)
    rec = opened(desk)
    desk.manual_close(rec["trade_id"], Q(), NOW + timedelta(minutes=1))
    again = make_desk(tmp_path)
    assert again.fault is None
    report = recover(tmp_path, initial_capital=again.config.capital)
    assert report.ok and not report.differences and not report.orphans
    assert journal_events(tmp_path) == ["paper.pending", "paper.open", "paper.close"]


def test_recovery_refuses_a_journal_it_cannot_trust_and_changes_nothing(tmp_path: Path) -> None:
    desk = make_desk(tmp_path)
    opened(desk)
    journal = tmp_path / "paper_journal.jsonl"
    lines = [json.loads(x) for x in journal.read_text(encoding="utf-8").splitlines()]
    for line in lines:
        line.pop("broker_position", None)  # an old-format journal
    journal.write_text("\n".join(json.dumps(x) for x in lines) + "\n", encoding="utf-8")
    state_before = (tmp_path / "paper_desk.json").read_text(encoding="utf-8")
    report = recover(tmp_path, initial_capital=10_000.0, apply=True)
    assert not report.applied and any("not complete enough" in n for n in report.notes)
    assert (tmp_path / "paper_desk.json").read_text(encoding="utf-8") == state_before


def test_the_journal_replay_matches_the_live_desk_state(tmp_path: Path) -> None:
    desk = make_desk(tmp_path)
    rec = opened(desk)
    replay = replay_journal(tmp_path / "paper_journal.jsonl")
    assert set(replay.trades) == {rec["trade_id"]} and not replay.orphans and not replay.problems
    assert list(replay.positions) == [rec["position_id"]]


# -- closure policy --------------------------------------------------------------------------------


def probe_at(minutes: int, kind: str = "WEEKEND") -> Any:
    def probe(now: datetime, horizon: int) -> tuple[datetime, str] | None:
        return (now + timedelta(minutes=minutes), kind) if minutes <= horizon else None

    return probe


def test_the_default_policy_blocks_an_entry_the_maximum_hold_could_carry_into_a_closure(
    tmp_path: Path,
) -> None:
    desk = make_desk(tmp_path)
    assert desk.config.closure_policy is ClosurePolicy.BLOCK_NEW_NEAR_CLOSE
    desk.closure_probe = probe_at(90)  # the weekly close is 90 minutes away; the hold is 120
    assert CLOSURE_NEAR in desk.can_open(NOW, "LONDON", 0.25, Q())
    with pytest.raises(DeskRefusal) as info:
        desk.open_from_decision(buy(), risk_pct=0.25, quote=Q(), spec=SPEC, now=NOW)
    assert info.value.code == CLOSURE_NEAR
    desk.closure_probe = probe_at(300)  # far enough: the hold ends first
    assert CLOSURE_NEAR not in desk.can_open(NOW, "LONDON", 0.25, Q())


def test_hold_across_close_never_blocks_and_close_before_closure_blocks_only_inside_the_buffer(
    tmp_path: Path,
) -> None:
    hold = make_desk(tmp_path / "hold", closure_policy=ClosurePolicy.HOLD_ACROSS_CLOSE)
    hold.closure_probe = probe_at(10)
    assert CLOSURE_NEAR not in hold.can_open(NOW, "LONDON", 0.25, Q())
    cbc = make_desk(tmp_path / "cbc", closure_policy=ClosurePolicy.CLOSE_BEFORE_CLOSURE)
    cbc.closure_probe = probe_at(60)
    assert CLOSURE_NEAR not in cbc.can_open(NOW, "LONDON", 0.25, Q()) and not cbc.closure_due(NOW)
    cbc.closure_probe = probe_at(3)  # inside the 5-minute buffer
    assert CLOSURE_NEAR in cbc.can_open(NOW, "LONDON", 0.25, Q()) and cbc.closure_due(NOW)


def test_a_trade_can_be_closed_for_the_closure_with_its_own_exit_reason(tmp_path: Path) -> None:
    desk = make_desk(tmp_path, closure_policy=ClosurePolicy.CLOSE_BEFORE_CLOSURE)
    rec = opened(desk)
    done = desk.manual_close(
        rec["trade_id"], Q(), NOW + timedelta(minutes=30), reason=DeskExit.CLOSURE_CLOSE.value
    )
    assert done["exit_reason"] == "CLOSURE_CLOSE" and done["status"] == PaperStatus.CLOSED
