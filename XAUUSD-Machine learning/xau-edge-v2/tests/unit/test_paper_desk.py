"""The paper desk with a real SQLite file: opening, management on bars, books, governor, restart."""

from __future__ import annotations

import sqlite3
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from tests.unit.test_core import CTX, SPEC, buy_state
from xau_edge_v2.core.decision import Decision, decide
from xau_edge_v2.domain.market import BrokerClock
from xau_edge_v2.paper.desk import MinuteBar, PaperDesk
from xau_edge_v2.paper.store import PaperStore

CLOCK = BrokerClock.parse("NY+7")
NOW = datetime(2026, 3, 3, 10, 0, 20, tzinfo=UTC)  # Tuesday, 20 s into the 10:00 minute
US = 1_000_000


def minute(offset: int) -> int:
    """Open time (µs) of the minute ``offset`` minutes after 10:00."""
    return int((NOW.replace(second=0).timestamp() + 60 * offset) * US)


def desk(path: Path, **kw: object) -> PaperDesk:
    return PaperDesk(
        PaperStore(path),
        start_equity=kw.pop("start_equity", 10_000.0),  # type: ignore[arg-type]
        auto=False,
        clock=CLOCK,
        **kw,  # type: ignore[arg-type]
    )


def buy_decision() -> Decision:
    d = decide(buy_state(), CTX)
    assert d.action == "BUY" and d.lots is not None
    return d


@pytest.fixture
def d(tmp_path: Path) -> PaperDesk:
    return desk(tmp_path / "paper.sqlite3")


def open_buy(desk_: PaperDesk, decision: Decision | None = None) -> dict[str, object]:
    row = desk_.open_position(NOW, decision or buy_decision(), SPEC, "MANUAL")
    assert row is not None
    return row


def test_open_fills_adverse_and_records_the_real_risk(d: PaperDesk) -> None:
    dec = buy_decision()
    row = open_buy(d, dec)
    assert row["quote_entry"] == dec.entry_price
    assert row["entry"] == pytest.approx(dec.entry_price + 0.03)  # type: ignore[operator]
    # risk is recomputed from the FILL: slightly above the planned risk, never below
    assert row["risk_amount"] > dec.risk_amount  # type: ignore[operator]
    assert row["status"] == "OPEN" and row["setup_id"] == dec.setup_id
    assert d.open_row() is not None and d.open_row()["id"] == row["id"]  # type: ignore[index]
    journal = d.journal()
    assert [j.kind for j in journal] == ["OPENED"] and journal[0].detail[
        "evidence"
    ] == "UNVALIDATED"


def test_a_setup_opens_once_even_if_asked_again_or_after_a_restart(tmp_path: Path) -> None:
    path = tmp_path / "p.sqlite3"
    first = desk(path)
    dec = buy_decision()
    assert first.open_position(NOW, dec, SPEC, "AUTO") is not None
    assert first.open_position(NOW + timedelta(seconds=3), dec, SPEC, "AUTO") is None
    first.store.close()
    second = desk(path)  # a restart
    assert second.open_position(NOW + timedelta(minutes=1), dec, SPEC, "AUTO") is None
    assert len(second.store.positions()) == 1 and len(second.journal()) == 1


def test_only_a_sized_buy_or_sell_can_open(d: PaperDesk) -> None:
    wait = decide(buy_state(m5_momentum="FLAT"), CTX)
    with pytest.raises(ValueError, match="BUY/SELL"):
        d.open_position(NOW, wait, SPEC, "AUTO")
    unsized = decide(buy_state(), replace(CTX, equity=None))
    assert unsized.action == "BUY" and unsized.lots is None
    with pytest.raises(ValueError, match="sized plan"):
        d.open_position(NOW, unsized, SPEC, "AUTO")


def hit_bars(sl: float, tp: float) -> tuple[MinuteBar, MinuteBar, MinuteBar]:
    """(a bar in the entry minute, a quiet bar, a stop bar) around a BUY plan."""
    mid = (sl + tp) / 2
    return (
        MinuteBar(minute(0), tp + 5, sl - 5, 20.0),  # the entry minute: must be ignored
        MinuteBar(minute(1), mid + 0.2, mid - 0.2, 20.0),
        MinuteBar(minute(2), mid, sl - 0.5, 20.0),
    )


def test_the_entry_minute_is_never_used_and_the_stop_closes_with_slippage(d: PaperDesk) -> None:
    row = open_buy(d)
    sl, tp = row["stop_loss"], row["take_profit"]
    entry_minute, quiet, stop_bar = hit_bars(sl, tp)  # type: ignore[arg-type]
    assert d.manage(NOW, [entry_minute], 2000.0, 2000.4) == []  # would have hit both, but pre-entry
    assert d.open_row() is not None
    assert d.manage(NOW, [entry_minute, quiet], 2000.0, 2000.4) == []
    closed = d.manage(NOW, [entry_minute, quiet, stop_bar], 2000.0, 2000.4)
    assert closed == [row["id"]]
    done = d.store.position(row["id"])  # type: ignore[arg-type]
    assert done is not None and done["status"] == "CLOSED" and done["exit_reason"] == "STOP_LOSS"
    assert done["exit_price"] == pytest.approx(sl - 0.03)  # type: ignore[operator]
    expected = (done["exit_price"] - row["entry"]) / 0.01 * 1.0 * row["lots"]  # type: ignore[operator]
    assert done["pnl_usd"] == pytest.approx(expected) and done["pnl_usd"] < 0
    assert done["closed_at"] == datetime.fromtimestamp(minute(2) / US + 60, UTC).isoformat()
    assert d.open_row() is None
    kinds = [j.kind for j in d.journal()]
    assert kinds == ["CLOSED", "OPENED"]  # newest first, append-only
    assert d.journal()[0].detail["reason"] == "STOP_LOSS" and d.journal()[0].detail["r"] < -1.0  # type: ignore[operator]


def test_the_target_closes_exactly_at_its_level_and_books_a_profit(d: PaperDesk) -> None:
    row = open_buy(d)
    tp = row["take_profit"]
    d.manage(NOW, [MinuteBar(minute(1), tp + 0.5, row["entry"], 20.0)], 2010.0, 2010.4)  # type: ignore[operator]
    done = d.store.position(row["id"])  # type: ignore[arg-type]
    assert done is not None and done["exit_reason"] == "TAKE_PROFIT" and done["exit_price"] == tp
    summary = d.summary(NOW, 0.25, 2010.0, 2010.4)
    assert summary.closed_count == 1 and summary.wins == 1 and summary.losses == 0
    assert summary.realized_pnl_usd == pytest.approx(done["pnl_usd"])
    assert summary.equity == pytest.approx(10_000.0 + done["pnl_usd"])
    assert summary.total_r > 1.5  # the plan paid more than 1.5 R before costs of slippage


def test_a_bar_touching_both_levels_is_flagged_and_takes_the_stop(d: PaperDesk) -> None:
    row = open_buy(d)
    wide = MinuteBar(minute(1), row["take_profit"] + 1, row["stop_loss"] - 1, 20.0)  # type: ignore[operator]
    d.manage(NOW, [wide], 2000.0, 2000.4)
    done = d.store.position(row["id"])  # type: ignore[arg-type]
    assert done is not None and done["exit_reason"] == "STOP_LOSS" and done["ambiguous"] == 1
    assert d.view(done, None, None).ambiguous is True


def test_mae_mfe_are_tracked_while_open_and_progress_is_remembered(d: PaperDesk) -> None:
    row = open_buy(d)
    entry = row["entry"]
    bar = MinuteBar(minute(1), entry + 0.8, entry - 0.5, 20.0)  # type: ignore[operator]
    d.manage(NOW, [bar], 2000.0, 2000.4)
    after = d.store.position(row["id"])  # type: ignore[arg-type]
    assert after is not None and after["status"] == "OPEN"
    assert after["last_bar_us"] == minute(1)
    assert after["mfe_points"] == pytest.approx(80.0) and after["mae_points"] == pytest.approx(50.0)
    d.manage(NOW, [bar], 2000.0, 2000.4)  # the same bar again changes nothing
    assert d.store.position(row["id"])["last_bar_us"] == minute(1)  # type: ignore[index]


def test_swap_is_charged_per_weekday_rollover_and_labelled_assumed(d: PaperDesk) -> None:
    row = open_buy(d)
    # close next day 15:00 UTC after one 17:00 New York roll (opened Tue 10:00 UTC = 05:00 NY)
    late = MinuteBar(
        int(datetime(2026, 3, 3, 23, 0, tzinfo=UTC).timestamp() * US),
        row["take_profit"] + 1,
        row["entry"],
        20.0,  # type: ignore[operator]
    )
    d.manage(NOW + timedelta(hours=14), [late], 2000.0, 2000.4)
    done = d.store.position(row["id"])  # type: ignore[arg-type]
    assert done is not None and done["swap_usd"] == pytest.approx(-76.05 * row["lots"])  # type: ignore[operator]
    view = d.view(done, None, None)
    assert view.net_pnl_usd == pytest.approx(done["pnl_usd"] + done["swap_usd"])


def test_books_include_floating_profit_and_the_summary_states_its_assumptions(d: PaperDesk) -> None:
    row = open_buy(d)
    floating = d.books(NOW, 2002.0, 2002.4)["floating"]
    assert floating == pytest.approx((2002.0 - row["entry"]) / 0.01 * row["lots"])  # type: ignore[operator]
    s = d.summary(NOW, 0.25, 2002.0, 2002.4)
    assert s.open_count == 1 and s.equity == pytest.approx(10_000.0 + floating)
    assert s.mode == "PAPER" and any("GIẢ ĐỊNH" in a for a in s.assumptions)
    assert s.governor.open_positions == 1 and "RISK_LIMIT" in s.governor.refusals


def test_a_loss_starts_the_cooldown_and_blocks_a_new_trade(d: PaperDesk) -> None:
    row = open_buy(d)
    d.manage(NOW, [MinuteBar(minute(1), row["entry"], row["stop_loss"] - 1, 20.0)], 1990.0, 1990.4)  # type: ignore[operator]
    later = NOW + timedelta(minutes=5)
    refusals = d.governor_refusals(later, 0.25, 1990.0, 1990.4)
    assert "COOLDOWN" in refusals
    status = d.governor_status(later, 0.25, 1990.0, 1990.4)
    assert status.cooldown_until is not None and status.loss_streak == 1
    assert d.governor_refusals(later + timedelta(minutes=40), 0.25, 1990.0, 1990.4) == []


def test_the_daily_loss_floor_flattens_open_positions(tmp_path: Path) -> None:
    small = desk(
        tmp_path / "p.sqlite3", start_equity=2_000.0
    )  # a tiny account: one stop is a big %
    dec = decide(buy_state(), replace(CTX, equity=2_000.0))
    assert dec.action == "BUY"
    row = small.open_position(NOW, dec, SPEC, "AUTO")
    assert row is not None
    # price far below the stop: floating loss beyond the 3.5% flatten floor
    closed = small.manage(NOW + timedelta(minutes=1), [], 1900.0, 1900.4)
    assert closed == [row["id"]]
    done = small.store.position(row["id"])  # type: ignore[arg-type]
    assert done is not None and done["exit_reason"] == "FLATTEN" and done["exit_price"] == 1900.0


def test_manual_close_uses_the_closing_side_of_the_quote(d: PaperDesk) -> None:
    row = open_buy(d)
    done = d.close_manual(row["id"], NOW + timedelta(minutes=2), 2001.0, 2001.4)  # type: ignore[arg-type]
    assert done is not None and done["exit_reason"] == "MANUAL" and done["exit_price"] == 2001.0
    assert d.close_manual(row["id"], NOW, 1.0, 2.0) is None  # type: ignore[arg-type]
    assert d.close_manual("nope", NOW, 1.0, 2.0) is None


def test_state_survives_a_restart_and_the_start_equity_is_never_rewritten(tmp_path: Path) -> None:
    path = tmp_path / "p.sqlite3"
    first = desk(path, start_equity=10_000.0)
    row = open_buy(first)
    first.store.close()
    second = desk(path, start_equity=999_999.0)  # a changed config must not rewrite history
    assert second.start_equity == 10_000.0
    assert second.open_row() is not None and second.open_row()["id"] == row["id"]  # type: ignore[index]
    second.manage(
        NOW, [MinuteBar(minute(1), row["take_profit"] + 1, row["entry"], 20.0)], 2010.0, 2010.4
    )  # type: ignore[operator]
    assert second.summary(NOW, 0.25, None, None).closed_count == 1
    assert second.store.revision() == 2  # opened + closed


def test_the_journal_is_append_only_and_changes_are_atomic(tmp_path: Path) -> None:
    store = PaperStore(tmp_path / "p.sqlite3")
    assert not [m for m in dir(store) if m.startswith(("delete", "update_journal", "edit"))]
    d_ = PaperDesk(store, start_equity=10_000.0, auto=False, clock=CLOCK)
    row = open_buy(d_)
    # a second INSERT with the same setup fails as a whole: no orphan journal row
    clash = dict(row)
    clash["id"] = "other"
    assert store.insert_position(clash, {"x": 1}) is False
    assert store.revision() == 1
    # closing something that is not open is refused and writes nothing
    assert store.close_position("missing", {"closed_at": NOW.isoformat()}, {}) is False
    assert store.revision() == 1
    with sqlite3.connect(tmp_path / "p.sqlite3") as raw:
        assert raw.execute("SELECT COUNT(*) FROM journal").fetchone()[0] == 1


def test_the_desk_can_not_express_a_broker_order() -> None:
    names = {n for n in dir(PaperDesk) if not n.startswith("_")}
    assert not {"send_order", "place_order", "order_send", "submit"} & names
    assert "mt5" not in PaperDesk.__module__.lower()
