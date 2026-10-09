"""Paper desk: lifecycle, idempotence, automatic exits, persistence; risk calculator; telemetry."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from typing import Any

import polars as pl
import pytest

from tests.unit.trading.helpers import SPEC, T0, aligned_state
from xau_edge.trading.baseline import BaselineConfig, DecisionContext, decide
from xau_edge.trading.governor import GovernorConfig
from xau_edge.trading.paper_desk import DeskConfig, DeskRefusal, PaperDesk, PaperStatus
from xau_edge.trading.position_manager import ManagerConfig
from xau_edge.trading.risk_calc import calculate
from xau_edge.trading.schema import Refusal, TradeDecision, TradingSignal
from xau_edge.trading.telemetry import DecisionTelemetry

NOW = aligned_state().timestamp


@dataclass(frozen=True)
class Q:
    bid: float = 2000.0
    ask: float = 2000.25
    spread_points: float = 25.0
    stale: bool = False


def buy(**over: Any) -> TradingSignal:
    s = decide(aligned_state(**over), DecisionContext(spec=SPEC, equity=10_000.0))
    assert s.decision is TradeDecision.BUY, s.refusal_reasons
    return s


def bars(
    rows: list[tuple[int, float, float, float, float]], start: Any = None, spread: int = 25
) -> pl.DataFrame:
    """M1 bars: (minute offset after ``start``, open, high, low, close)."""
    base = start or NOW
    return pl.DataFrame(
        {
            "timestamp": pl.Series(
                [base + timedelta(minutes=m) for m, *_ in rows], dtype=pl.Datetime("us", "UTC")
            ),
            "open": [r[1] for r in rows],
            "high": [r[2] for r in rows],
            "low": [r[3] for r in rows],
            "close": [r[4] for r in rows],
            "spread": [spread] * len(rows),
        }
    )


def make_desk(tmp_path: Path, **kw: Any) -> PaperDesk:
    return PaperDesk(tmp_path, DeskConfig(**kw), code_version="test-sha", clock=lambda: NOW)


def opened(
    desk: PaperDesk, decision: TradingSignal | None = None, risk: float = 0.25
) -> dict[str, Any]:
    return desk.open_from_decision(
        decision or buy(),
        risk_pct=risk,
        quote=Q(),
        spec=SPEC,
        now=NOW,
        market={"session": "LONDON"},
    )


# ---- lifecycle ---------------------------------------------------------------------------------


def test_open_fills_at_the_ask_plus_slippage_sizes_by_risk_and_journals(tmp_path: Path) -> None:
    desk = make_desk(tmp_path)
    rec = opened(desk)
    assert rec["status"] == PaperStatus.OPEN
    assert rec["fill_price"] == pytest.approx(2000.25 + 0.03)  # ask + 3 points of assumed slippage
    assert 0.0 < rec["lots"] <= 1.0
    sl_distance = abs(rec["fill_price"] - rec["initial_sl"])
    assert rec["lots"] * sl_distance * 100 <= 10_000 * 0.0025 + 1e-6  # never above 0.25% of equity
    journal = [
        json.loads(x)
        for x in (tmp_path / "paper_journal.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert [j["event"] for j in journal] == ["paper.pending", "paper.open"]
    assert journal[1]["code_version"] == "test-sha"
    assert journal[1]["decision"]["strategy_version"] and journal[1]["market"] == {
        "session": "LONDON"
    }


def test_a_wait_an_expired_setup_a_stale_quote_and_a_bad_risk_are_refused(tmp_path: Path) -> None:
    desk = make_desk(tmp_path)
    wait = decide(aligned_state(h1_trend="NEUTRAL"), DecisionContext(spec=SPEC, equity=10_000.0))
    with pytest.raises(DeskRefusal) as exc:
        opened(desk, wait)
    assert exc.value.code == "NOT_ACTIONABLE"
    good = buy()
    assert good.signal_expiry is not None
    with pytest.raises(DeskRefusal) as exc:
        desk.open_from_decision(
            good, risk_pct=0.25, quote=Q(), spec=SPEC, now=good.signal_expiry + timedelta(seconds=1)
        )
    assert exc.value.code == "EXPIRED"
    with pytest.raises(DeskRefusal) as exc:
        desk.open_from_decision(good, risk_pct=0.25, quote=Q(stale=True), spec=SPEC, now=NOW)
    assert exc.value.code == "QUOTE_STALE"
    for bad in (0.0, 0.3, 1.0, 5.0):
        with pytest.raises(DeskRefusal) as exc:
            opened(desk, good, risk=bad)
        assert exc.value.code == "RISK_PCT_NOT_ALLOWED"
    with pytest.raises(DeskRefusal) as exc:
        desk.open_from_decision(good, risk_pct=0.25, quote=Q(), spec=None, now=NOW)
    assert exc.value.code == "NO_SYMBOL_SPEC"
    assert desk.open_trade() is None


def test_one_order_per_setup_and_one_position_at_a_time(tmp_path: Path) -> None:
    desk = make_desk(tmp_path)
    decision = buy()
    opened(desk, decision)
    with pytest.raises(DeskRefusal) as exc:
        opened(desk, decision)
    assert exc.value.code == "DUPLICATE_SETUP"
    other = decision.model_copy(update={"setup_id": "another-setup"})
    with pytest.raises(DeskRefusal) as exc:
        opened(desk, other)
    assert exc.value.code == Refusal.RISK_LIMIT.value  # the governor: a position is already open


def test_a_fill_far_from_the_plan_is_cancelled_not_taken(tmp_path: Path) -> None:
    desk = make_desk(tmp_path)
    rec = desk.open_from_decision(
        buy(), risk_pct=0.25, quote=Q(bid=2001.5, ask=2001.75), spec=SPEC, now=NOW
    )
    assert rec["status"] == PaperStatus.CANCELLED
    assert rec["cancel_reason"] == "ENTRY_DRIFT"
    assert desk.open_trade() is None
    again = desk.open_from_decision(
        buy(), risk_pct=0.25, quote=Q(), spec=SPEC, now=NOW
    )  # the setup may be retried
    assert again["status"] == PaperStatus.OPEN


# ---- automatic exits ---------------------------------------------------------------------------


def test_stop_loss_closes_with_reason_r_and_excursions(tmp_path: Path) -> None:
    desk = make_desk(tmp_path)
    rec = opened(desk)
    sl, entry = rec["sl"], rec["fill_price"]
    stop_bar = bars([(1, entry, entry + 0.4, sl - 0.5, sl - 0.2)])
    closed = desk.process_bars(stop_bar)
    assert len(closed) == 1
    assert closed[0]["exit_reason"] == "STOP_LOSS"
    assert closed[0]["status"] == PaperStatus.CLOSED
    assert closed[0]["r_multiple"] == pytest.approx(
        -1.0, abs=0.12
    )  # one R plus spread/slippage cost
    assert desk.open_trade() is None
    assert desk.process_bars(stop_bar) == []  # the same bar again cannot close a second time


def test_take_profit_and_the_stop_wins_when_one_bar_touches_both(tmp_path: Path) -> None:
    desk = make_desk(tmp_path)
    rec = opened(desk)
    tp, sl = rec["tp"], rec["sl"]
    closed = desk.process_bars(bars([(1, 2000.3, tp + 0.5, 2000.0, tp)]))
    assert closed[0]["exit_reason"] == "TAKE_PROFIT"
    assert closed[0]["r_multiple"] > 1.0
    assert closed[0]["mfe_r"] >= 1.0
    desk2 = make_desk(tmp_path / "second")
    rec2 = opened(desk2)
    both = desk2.process_bars(bars([(1, 2000.3, rec2["tp"] + 1, rec2["sl"] - 1, 2000.3)]))
    assert both[0]["exit_reason"] == "STOP_LOSS"  # pessimistic: the stop is assumed first
    assert sl < rec["fill_price"]


def test_time_exit_after_the_maximum_hold(tmp_path: Path) -> None:
    desk = make_desk(tmp_path, max_hold_minutes=3)
    rec = opened(desk)
    quiet = [(m, 2000.2, 2000.5, 1999.9, 2000.2) for m in range(1, 6)]
    closed = desk.process_bars(bars(quiet))
    assert [c["exit_reason"] for c in closed] == ["TIME_EXIT"]
    assert rec["status"] == PaperStatus.CLOSED
    assert closed[0]["duration_minutes"] >= 3


def test_the_bar_in_which_the_entry_happened_is_never_used(tmp_path: Path) -> None:
    desk = make_desk(tmp_path)
    rec = opened(desk)
    before_entry = bars([(-1, 2000.0, 2010.0, rec["sl"] - 5, 2000.0)])  # opened before the entry
    assert desk.process_bars(before_entry) == []
    assert desk.open_trade() is not None


def test_short_exits_are_judged_on_the_ask_side(tmp_path: Path) -> None:
    desk = make_desk(tmp_path)
    sell_state = aligned_state(
        h4_regime="TREND_DOWN", h1_trend="BEARISH", m30_structure="DOWN", m15_structure="DOWN",
        m15_pullback="PULLBACK_IN_DOWNTREND", m5_momentum="DOWN", m1_micro_state="ACTIVE_DOWN",
        distance_to_support=20.0, distance_to_resistance=3.0,
        recent_swing_high=2003.0, recent_swing_low=1990.0,
    )  # fmt: skip
    sell = decide(sell_state, DecisionContext(spec=SPEC, equity=10_000.0))
    assert sell.decision is TradeDecision.SELL, sell.refusal_reasons
    rec = desk.open_from_decision(sell, risk_pct=0.25, quote=Q(), spec=SPEC, now=NOW)
    assert rec["status"] == PaperStatus.OPEN
    assert rec["fill_price"] == pytest.approx(2000.0 - 0.03)  # bid minus slippage
    # the bid high is one spread (0.25) below the stop: the ASK reaches it, so the stop must fire
    hit = desk.process_bars(bars([(1, 2000.0, rec["sl"] - 0.1, 1999.5, 2000.0)]))
    assert hit[0]["exit_reason"] == "STOP_LOSS"


def test_manual_close_requires_an_open_trade_and_cannot_repeat(tmp_path: Path) -> None:
    desk = make_desk(tmp_path)
    rec = opened(desk)
    done = desk.manual_close(
        rec["trade_id"], Q(bid=2000.6, ask=2000.85), NOW + timedelta(minutes=2)
    )
    assert done["exit_reason"] == "MANUAL_CLOSE"
    assert done["status"] == PaperStatus.CLOSED
    with pytest.raises(DeskRefusal) as exc:
        desk.manual_close(rec["trade_id"], Q(), NOW)
    assert exc.value.code == "NOT_OPEN"
    with pytest.raises(DeskRefusal) as exc:
        desk.manual_close("T99999", Q(), NOW)
    assert exc.value.code == "NOT_FOUND"


def test_invalidation_closes_only_when_enabled_and_break_even_tightens_the_stop(
    tmp_path: Path,
) -> None:
    off = make_desk(tmp_path / "off")
    rec = opened(off)
    still = [(1, 2000.3, 2000.6, 2000.1, 2000.4)]
    assert off.process_bars(bars(still), invalidated={"BUY": True}) == []
    on = make_desk(
        tmp_path / "on", manager=ManagerConfig(close_on_invalidation=True, max_hold_minutes=10**7)
    )
    opened(on)
    closed = on.process_bars(bars(still), invalidated={"BUY": True})
    assert closed[0]["exit_reason"] == "INVALIDATED"
    be = make_desk(
        tmp_path / "be",
        manager=ManagerConfig(break_even_enabled=True, break_even_at_r=1.0, max_hold_minutes=10**7),
    )
    be_rec = opened(be)
    risk = be_rec["fill_price"] - be_rec["initial_sl"]
    be.process_bars(bars([(1, 2000.3, be_rec["fill_price"] + 1.2 * risk, 2000.2, 2000.5)]))
    assert be_rec["sl"] > be_rec["initial_sl"]
    assert be_rec["stage"] == "BREAK_EVEN"
    assert rec["status"] == PaperStatus.OPEN


# ---- persistence and governance ----------------------------------------------------------------


def test_state_survives_a_restart_and_a_setup_is_never_taken_twice(tmp_path: Path) -> None:
    desk = make_desk(tmp_path)
    decision = buy()
    rec = opened(desk, decision)
    reborn = make_desk(tmp_path)
    assert reborn.open_trade() is not None
    assert reborn.open_trade()["trade_id"] == rec["trade_id"]  # type: ignore[index]
    with pytest.raises(DeskRefusal) as exc:
        reborn.open_from_decision(decision, risk_pct=0.25, quote=Q(), spec=SPEC, now=NOW)
    assert exc.value.code == "DUPLICATE_SETUP"
    closed = reborn.process_bars(bars([(1, 2000.3, 2000.6, rec["sl"] - 1, rec["sl"] - 0.5)]))
    assert len(closed) == 1
    assert make_desk(tmp_path).closed_trades()[0]["exit_reason"] == "STOP_LOSS"


def test_a_losing_trade_starts_a_cooldown_and_the_daily_summary_counts_it(tmp_path: Path) -> None:
    desk = make_desk(tmp_path, governor=GovernorConfig(cooldown_after_loss_minutes=30))
    rec = opened(desk)
    desk.process_bars(bars([(1, 2000.3, 2000.6, rec["sl"] - 1, rec["sl"] - 0.5)]))
    later = buy().model_copy(update={"setup_id": "next-setup"})
    with pytest.raises(DeskRefusal) as exc:
        desk.open_from_decision(
            later, risk_pct=0.25, quote=Q(), spec=SPEC, now=NOW + timedelta(minutes=5)
        )
    assert exc.value.code == Refusal.COOLDOWN.value
    summary = desk.day_summary(NOW + timedelta(minutes=5))
    assert (summary["paper_trades"], summary["wins"], summary["losses"], summary["open"]) == (
        1,
        0,
        1,
        0,
    )


def test_equity_and_unrealized_pnl_use_the_exit_side_of_the_quote(tmp_path: Path) -> None:
    desk = make_desk(tmp_path)
    rec = opened(desk)
    view = desk.position_view(
        Q(bid=rec["fill_price"] + 1.0, ask=rec["fill_price"] + 1.25), NOW + timedelta(minutes=3)
    )
    assert view is not None
    assert view["current_price"] == pytest.approx(
        rec["fill_price"] + 1.0
    )  # a long marks at the bid
    assert view["unrealized_pnl"] == pytest.approx(rec["lots"] * 100.0, rel=1e-6)
    assert view["unrealized_r"] > 0
    assert view["duration_minutes"] == pytest.approx(3.0)
    acct = desk.account(Q(bid=rec["fill_price"] + 1.0, ask=rec["fill_price"] + 1.25), NOW)
    assert acct["simulated"] is True


# ---- risk calculator ---------------------------------------------------------------------------


def test_risk_calculator_matches_a_hand_calculation_and_only_changes_lots() -> None:
    plan = calculate(
        equity=10_000.0,
        risk_pct=0.25,
        entry=2000.0,
        stop_loss=1995.0,
        spec=SPEC,
        take_profit=2010.0,
    )
    # 0.25% of 10,000 = 25 USD; a 5.00 stop costs 500 USD per lot -> 0.05 lot
    assert plan.ok
    assert plan.lots == pytest.approx(0.05)
    assert plan.risk_amount == pytest.approx(25.0)
    assert plan.loss_at_sl == pytest.approx(25.0)
    assert plan.gain_at_tp == pytest.approx(50.0)
    assert plan.sl_distance == pytest.approx(5.0)
    bigger = calculate(equity=10_000.0, risk_pct=0.50, entry=2000.0, stop_loss=1995.0, spec=SPEC)
    assert bigger.lots == pytest.approx(0.10)
    smaller = calculate(equity=10_000.0, risk_pct=0.10, entry=2000.0, stop_loss=1995.0, spec=SPEC)
    assert smaller.lots == pytest.approx(0.02)


def test_risk_calculator_rounds_down_refuses_tiny_budgets_and_bad_inputs() -> None:
    odd = calculate(equity=10_000.0, risk_pct=0.25, entry=2000.0, stop_loss=1993.0, spec=SPEC)
    assert odd.lots == pytest.approx(0.03)  # 25/700 = 0.0357 rounded DOWN to the 0.01 step
    assert odd.risk_pct_actual <= 0.25
    tiny = calculate(equity=500.0, risk_pct=0.10, entry=2000.0, stop_loss=1990.0, spec=SPEC)
    assert not tiny.ok
    assert "MIN_LOT_EXCEEDS_RISK" in tiny.errors
    for bad in (0.0, 0.3, 2.0):
        assert (
            "RISK_PCT_NOT_ALLOWED"
            in calculate(
                equity=10_000.0, risk_pct=bad, entry=2000.0, stop_loss=1995.0, spec=SPEC
            ).errors
        )
    assert not calculate(
        equity=float("nan"), risk_pct=0.25, entry=2000.0, stop_loss=1995.0, spec=SPEC
    ).ok


# ---- telemetry ---------------------------------------------------------------------------------


def test_telemetry_counts_decisions_and_the_most_common_blocker(tmp_path: Path) -> None:
    tele = DecisionTelemetry(tmp_path)
    ctx = DecisionContext(spec=SPEC, equity=10_000.0)
    cfg = BaselineConfig()
    tele.append(decide(aligned_state(), ctx, cfg), at=NOW)
    for i in range(3):
        tele.append(
            decide(
                aligned_state(m5_momentum="FLAT", timestamp=NOW + timedelta(minutes=i + 1)),
                ctx,
                cfg,
            ),
            at=NOW + timedelta(minutes=i + 1),
        )
    tele.append(
        decide(aligned_state(h1_trend="NEUTRAL", timestamp=NOW + timedelta(minutes=9)), ctx, cfg),
        at=NOW + timedelta(minutes=9),
    )
    with (tmp_path / f"decisions-{NOW:%Y%m%d}.jsonl").open("a", encoding="utf-8") as handle:
        handle.write("{torn")  # a torn last line is skipped
    summary = tele.summary(NOW)
    assert (summary["buy"], summary["sell"], summary["wait"], summary["decisions"]) == (1, 0, 4, 5)
    assert summary["most_common_blocker"] == "NO_TRIGGER"
    assert summary["distinct_setups"] == 1
    assert summary["wait_pct"] == 80.0
    assert T0 < NOW


def test_a_stopped_trade_never_shows_an_excursion_beyond_its_stop_or_the_bar_that_stopped_it(
    tmp_path: Path,
) -> None:
    desk = make_desk(tmp_path)
    rec = opened(desk)
    entry, sl = rec["fill_price"], rec["sl"]
    risk = entry - sl
    # a wild bar: it spikes far above (never credited: the stop is judged first) and far below
    wild = bars([(1, entry, entry + 3 * risk, sl - 2 * risk, sl - risk)])
    done = desk.process_bars(wild)[0]
    assert done["exit_reason"] == "STOP_LOSS"
    assert done["mae_r"] == pytest.approx(1.0, abs=0.05)  # not 3R: it ended at the stop
    assert done["mfe_r"] == pytest.approx(0.0, abs=0.01)  # nothing credited from the stopping bar


def test_mfe_of_a_stopped_trade_keeps_what_happened_before_the_stopping_bar(tmp_path: Path) -> None:
    desk = make_desk(tmp_path)
    rec = opened(desk)
    entry, sl = rec["fill_price"], rec["sl"]
    risk = entry - sl
    desk.process_bars(bars([(1, entry, entry + 0.8 * risk, entry - 0.2 * risk, entry)]))
    done = desk.process_bars(bars([(2, entry, entry + 5 * risk, sl - 0.5, sl)]))[0]
    assert done["exit_reason"] == "STOP_LOSS"
    assert done["mfe_r"] == pytest.approx(0.8, abs=0.1)
    assert done["mae_r"] <= 1.1


def test_a_target_exit_does_not_credit_more_than_the_target(tmp_path: Path) -> None:
    desk = make_desk(tmp_path)
    rec = opened(desk)
    entry, tp = rec["fill_price"], rec["tp"]
    done = desk.process_bars(bars([(1, entry + 0.1, tp + 10, entry, tp + 5)]))[0]
    assert done["exit_reason"] == "TAKE_PROFIT"
    assert done["mfe_r"] == pytest.approx((tp - entry) / (entry - rec["sl"]), abs=0.05)


def _opened_mid_bar(desk: PaperDesk) -> dict[str, Any]:
    return desk.open_from_decision(
        buy(), risk_pct=0.25, quote=Q(), spec=SPEC, now=NOW + timedelta(seconds=30)
    )


def test_a_stop_hit_inside_the_minute_of_the_fill_is_not_missed(tmp_path: Path) -> None:
    desk = make_desk(tmp_path)
    rec = _opened_mid_bar(desk)
    entry, sl = rec["fill_price"], rec["sl"]
    # the minute that contains the fill: it dives through the stop and recovers by its close
    done = desk.process_bars(bars([(0, entry, entry + 0.2, sl - 0.5, entry + 0.1)]))
    assert len(done) == 1 and done[0]["exit_reason"] == "STOP_LOSS"


def test_a_target_touched_inside_the_minute_of_the_fill_is_not_credited(tmp_path: Path) -> None:
    desk = make_desk(tmp_path)
    rec = _opened_mid_bar(desk)
    entry, tp = rec["fill_price"], rec["tp"]
    done = desk.process_bars(bars([(0, entry, tp + 1.0, entry - 0.1, entry + 0.1)]))
    assert (
        done == [] and desk.open_trade() is not None
    )  # favourable extremes of that minute are ignored
    # and the position is not managed (no exit by time, no stop moves) on that bar
    assert desk.open_trade()["mfe"] == pytest.approx(0.0, abs=1e-9)  # type: ignore[index]


def test_a_corrupt_state_file_is_set_aside_and_reported_not_silently_replaced(
    tmp_path: Path,
) -> None:
    desk = make_desk(tmp_path)
    opened(desk)
    (tmp_path / "paper_desk.json").write_text("{not json", encoding="utf-8")
    fresh = make_desk(tmp_path)
    assert fresh.trades == {}
    assert fresh.load_error is not None and "EMPTY" in fresh.load_error
    assert list(tmp_path.glob("paper_desk.json.corrupt-*"))  # the broken file is kept for forensics


def test_a_fill_that_crashes_leaves_a_cancelled_trade_not_a_stuck_pending_one(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    desk = make_desk(tmp_path)

    def boom(_order: object) -> object:
        raise KeyError("unexpected broker failure")

    monkeypatch.setattr(desk.broker, "submit_order", boom)
    rec = opened(desk)
    assert rec["status"] == PaperStatus.CANCELLED
    assert desk.open_trade() is None
    assert all(r["status"] != PaperStatus.PENDING for r in desk.trades.values())
