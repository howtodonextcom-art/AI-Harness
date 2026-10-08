"""Backtest engine mechanics on hand-built M5 bars (bid prices, spread in points).

Reference numbers: price 100.00, spread 20 points (0.20), slippage 3 points (0.03), ATR 2.0,
stop 1.5 ATR (3.00), target 3.0 ATR (6.00), equity 100,000, risk 0.5% (500) -> 1.66 lots,
actual risk 498 USD.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import Any

import polars as pl
import pytest

from xau_edge.backtest.costs import CostModel
from xau_edge.backtest.engine import BacktestConfig, prop_breaches, run_backtest
from xau_edge.domain.timeframe import Timeframe
from xau_edge.news.calendar import EventImpact, NewsEvent, StaticCalendar
from xau_edge.risk.engine import RiskLimits
from xau_edge.risk.prop_rules import PropProfile

T0 = datetime(2026, 3, 2, 10, 0, tzinfo=UTC)  # a Monday, winter time
PROFILE = PropProfile(
    name="t",
    source="x",
    verified_on="2026-01-01",
    daily_loss_limit_pct=5.0,
    max_loss_limit_pct=10.0,
    max_loss_kind="static",
    internal_buffer_pct_of_limit=0.0,
)


def _bars(n: int = 40, start: datetime = T0, **overrides: dict[int, float]) -> pl.DataFrame:
    """Flat market at 100.00; ``overrides`` maps column -> {bar index: value}."""
    cols: dict[str, list[float]] = {
        "open": [100.0] * n,
        "high": [100.1] * n,
        "low": [99.9] * n,
        "close": [100.0] * n,
        "spread": [20.0] * n,
    }
    for col, changes in overrides.items():
        for i, v in changes.items():
            cols[col][i] = v
    ts = [start + timedelta(minutes=5 * i) for i in range(n)]
    return pl.DataFrame(
        {"timestamp": pl.Series(ts, dtype=pl.Datetime("us", "UTC")), **cols}
    ).with_columns(pl.col("spread").cast(pl.Float64))


def _signal(direction: int = 1, at: datetime = T0, **over: Any) -> pl.DataFrame:
    row: dict[str, Any] = {
        "timestamp": at - timedelta(minutes=5),
        "decision_time": at,
        "direction": direction,
        "atr": 2.0,
        "stop_atr": 1.5,
        "target_atr": 3.0,
        "max_hold_bars": 12,
        "strategy": "t",
        "regime": "RANGE",
    }
    row.update(over)
    return pl.DataFrame([row]).with_columns(
        pl.col("timestamp").cast(pl.Datetime("us", "UTC")),
        pl.col("decision_time").cast(pl.Datetime("us", "UTC")),
        pl.col("direction").cast(pl.Int8),
        pl.col("max_hold_bars").cast(pl.Int32),
    )


def _cfg(**over: Any) -> BacktestConfig:
    base: dict[str, Any] = {
        "signal_timeframe": Timeframe.M5,
        "require_news_calendar": False,
        "costs": CostModel(slippage_points=3.0, swap_long_points=0.0, swap_short_points=0.0),
    }
    base.update(over)
    return BacktestConfig(**base)


def _run(signals: pl.DataFrame, bars: pl.DataFrame, cfg: BacktestConfig | None = None):  # type: ignore[no-untyped-def]
    return run_backtest(signals, bars, cfg or _cfg(), PROFILE)


def test_long_target_hit_pays_exactly_two_r_before_costs_other_than_spread_and_slippage() -> None:
    res = _run(_signal(1), _bars(high={3: 106.5}))
    t = res.trades.row(0, named=True)
    assert res.trades.height == 1
    assert t["lots"] == pytest.approx(1.66)
    assert t["entry_price"] == pytest.approx(100.23)  # ask: open + spread + slippage
    assert t["exit_reason"] == "TARGET"
    assert t["exit_price"] == pytest.approx(106.23)  # entry + 6.00, no slippage on a limit
    assert t["gross_pnl"] == pytest.approx(6.0 * 1.66 * 100)
    assert t["net_pnl"] == pytest.approx(996.0)
    assert t["net_r"] == pytest.approx(996.0 / 498.0)
    assert t["exit_time"] == T0 + timedelta(minutes=15)


def test_long_stop_hit_loses_a_little_more_than_one_r_because_of_slippage() -> None:
    res = _run(_signal(1), _bars(low={2: 96.9}))
    t = res.trades.row(0, named=True)
    assert t["exit_reason"] == "STOP"
    assert t["exit_price"] == pytest.approx(97.23 - 0.03)
    assert t["net_pnl"] == pytest.approx((97.20 - 100.23) * 1.66 * 100)
    assert t["net_r"] < -1.0


def test_short_uses_bid_entry_and_ask_triggered_exits() -> None:
    # short entry = open - slippage = 99.97 ; stop = 102.97 (needs high + spread >= 102.97)
    miss = _run(_signal(-1), _bars(high={3: 102.7}))
    assert miss.trades["exit_reason"][0] == "TIME"
    hit = _run(_signal(-1), _bars(high={3: 102.8}))
    t = hit.trades.row(0, named=True)
    assert t["entry_price"] == pytest.approx(99.97)
    assert t["exit_reason"] == "STOP"
    assert t["exit_price"] == pytest.approx(102.97 + 0.03)
    # target 93.97 needs ask low <= 93.97: low <= 93.77
    tgt = _run(_signal(-1), _bars(low={4: 93.7}))
    assert tgt.trades["exit_reason"][0] == "TARGET"
    assert tgt.trades["exit_price"][0] == pytest.approx(93.97)


def test_a_bar_touching_both_barriers_resolves_to_the_stop() -> None:
    res = _run(_signal(1), _bars(high={2: 110.0}, low={2: 90.0}))
    assert res.trades["exit_reason"][0] == "STOP"


def test_gap_through_the_stop_fills_at_the_open_not_at_the_stop() -> None:
    res = _run(_signal(1), _bars(open={5: 95.0}, high={5: 95.2}, low={5: 94.8}, close={5: 95.0}))
    t = res.trades.row(0, named=True)
    assert t["exit_reason"] == "STOP"
    assert t["exit_price"] == pytest.approx(95.0)


def test_time_exit_uses_the_last_allowed_bar_close_with_adverse_slippage() -> None:
    res = _run(_signal(1, max_hold_bars=12), _bars(close={11: 100.5}, high={11: 100.6}))
    t = res.trades.row(0, named=True)
    assert t["exit_reason"] == "TIME"
    assert t["exit_time"] == T0 + timedelta(minutes=5 * 11)
    assert t["exit_price"] == pytest.approx(100.5 - 0.03)


def test_hold_is_converted_from_signal_bars_to_execution_bars() -> None:
    res = _run(
        _signal(1, max_hold_bars=2),
        _bars(),
        _cfg(signal_timeframe=Timeframe.M15),
    )
    assert res.trades["exit_time"][0] == T0 + timedelta(minutes=5 * 5)  # 2 x 15 min = 6 exec bars


def test_entry_is_the_open_of_the_first_bar_at_or_after_the_decision_time() -> None:
    res = _run(_signal(1, at=T0 + timedelta(minutes=7)), _bars())
    assert res.trades["entry_time"][0] == T0 + timedelta(minutes=10)


def test_entry_across_a_large_gap_is_skipped() -> None:
    bars = _bars(20).vstack(_bars(20, start=T0 + timedelta(days=2)))
    res = _run(_signal(1, at=T0 + timedelta(minutes=5 * 20)), bars)
    assert res.trades.height == 0
    assert res.skipped["reason"][0] == "ENTRY_GAP"


def test_signals_during_an_open_position_are_skipped() -> None:
    sig = pl.concat([_signal(1, at=T0), _signal(1, at=T0 + timedelta(minutes=10))])
    res = _run(sig, _bars(high={5: 120.0}))
    assert res.trades.height == 1
    assert res.skipped["reason"].to_list() == ["IN_POSITION"]


def test_a_following_signal_after_the_exit_is_taken() -> None:
    sig = pl.concat([_signal(1, at=T0), _signal(1, at=T0 + timedelta(minutes=25))])
    res = _run(sig, _bars(high={2: 120.0}))
    assert res.trades.height == 2


def test_wide_spread_is_refused_by_the_risk_engine() -> None:
    res = _run(_signal(1), _bars(spread={0: 400.0}))
    assert res.trades.height == 0
    assert "SPREAD" in res.skipped["reason"][0]


def test_regime_column_feeds_the_volatility_guard() -> None:
    res = _run(_signal(1, regime="SHOCK"), _bars())
    assert res.trades.height == 0
    assert "VOLATILITY" in res.skipped["reason"][0]


def test_swap_is_charged_for_each_rollover_crossed() -> None:
    # 17:00 New York = 22:00 UTC in March (before US DST). Enter 21:50, hold past 22:00.
    start = datetime(2026, 3, 2, 21, 50, tzinfo=UTC)
    costs = CostModel(slippage_points=3.0, swap_long_points=-76.05, swap_short_points=-4.2)
    cfg = _cfg(costs=costs)
    long = run_backtest(_signal(1, at=start), _bars(start=start), cfg, PROFILE)
    t = long.trades.row(0, named=True)
    assert t["swap"] == pytest.approx(-76.05 * 1.66)
    short = run_backtest(_signal(-1, at=start), _bars(start=start), cfg, PROFILE)
    assert short.trades["swap"][0] == pytest.approx(-4.2 * short.trades["lots"][0])
    flat = run_backtest(_signal(1, at=T0), _bars(), cfg, PROFILE)
    assert flat.trades["swap"][0] == 0.0  # 10:00-11:00 UTC crosses no rollover


def test_commission_is_charged_on_both_sides() -> None:
    cfg = _cfg(
        costs=CostModel(
            slippage_points=3.0,
            commission_per_lot_per_side=3.5,
            swap_long_points=0.0,
            swap_short_points=0.0,
        )
    )
    res = _run(_signal(1), _bars(high={3: 106.5}), cfg)
    t = res.trades.row(0, named=True)
    assert t["commission"] == pytest.approx(2 * 3.5 * 1.66)
    assert t["net_pnl"] == pytest.approx(t["gross_pnl"] - t["commission"] + t["swap"])


def test_balance_compounds_across_trades_and_sizing_follows_equity() -> None:
    sig = pl.concat([_signal(1, at=T0), _signal(1, at=T0 + timedelta(minutes=25))])
    res = _run(sig, _bars(high={2: 120.0, 7: 120.0}))
    first, second = res.trades["lots"].to_list()
    assert second >= first  # equity grew after a winner
    assert res.trades["balance_after"][1] == pytest.approx(100_000 + res.trades["net_pnl"].sum())


def test_equity_curve_tracks_floating_pnl_and_ends_at_the_final_balance() -> None:
    res = _run(
        _signal(1), _bars(close={1: 101.0, 2: 99.0}, high={1: 101.1, 6: 110.0}, low={2: 98.9})
    )
    eq = res.equity
    assert eq.height == 40
    assert eq["equity"][0] == pytest.approx(
        100_000 - (100.23 - 100.0) * 1.66 * 100
    )  # floating at bar 0
    assert eq["equity"][1] == pytest.approx(100_000 + (101.0 - 100.23) * 1.66 * 100)
    assert eq["equity"][2] == pytest.approx(100_000 + (99.0 - 100.23) * 1.66 * 100)
    assert eq["equity"][-1] == pytest.approx(res.trades["balance_after"][-1])


def test_consecutive_losses_stop_new_entries_for_the_day() -> None:
    sigs = pl.concat([_signal(1, at=T0 + timedelta(minutes=30 * i)) for i in range(5)])
    bars = _bars(80, low={i: 90.0 for i in range(80) if i % 6 == 1})
    res = _run(sigs, bars)
    assert res.trades.height == 3
    assert any("CONSECUTIVE_LOSSES" in r for r in res.skipped["reason"].to_list())


def test_kill_switch_latches_after_a_prop_breach() -> None:
    tight = PropProfile(
        name="t",
        source="x",
        verified_on="2026-01-01",
        daily_loss_limit_pct=0.8,
        max_loss_limit_pct=10.0,
        max_loss_kind="static",
        internal_buffer_pct_of_limit=0.0,
    )
    # a gap through the stop loses ~870 USD > the 800 USD daily limit: the next signal is blocked
    sigs = pl.concat([_signal(1, at=T0), _signal(1, at=T0 + timedelta(minutes=60))])
    bars = _bars(40, open={2: 95.0}, high={2: 95.2}, low={2: 94.8}, close={2: 95.0})
    res = run_backtest(sigs, bars, _cfg(), tight)
    assert res.trades.height == 1
    assert "KILL_SWITCH" in res.skipped["reason"][0]
    assert res.kill_switch_reason.startswith("PROP_BREACH")


def test_prop_breaches_are_found_from_the_equity_curve() -> None:
    ts = [T0 + timedelta(hours=i) for i in range(6)]
    equity = [100_000.0, 99_000.0, 94_500.0, 96_000.0, 100_000.0, 89_000.0]
    frame = pl.DataFrame(
        {"timestamp": pl.Series(ts, dtype=pl.Datetime("us", "UTC")), "equity": equity}
    )
    out = prop_breaches(frame, PROFILE, initial_capital=100_000.0)
    assert out["daily"] == [date(2026, 3, 2)]
    assert out["max_loss"] is True
    ok = prop_breaches(frame.head(2), PROFILE, initial_capital=100_000.0)
    assert ok["daily"] == []
    assert ok["max_loss"] is False


def test_unsorted_or_invalid_inputs_are_rejected() -> None:
    with pytest.raises(ValueError, match="sorted"):
        _run(_signal(1), _bars().reverse())
    with pytest.raises(ValueError, match="column"):
        _run(_signal(1).drop("atr"), _bars())
    with pytest.raises(ValueError, match="direction"):
        _run(_signal(2), _bars())


def test_result_is_deterministic() -> None:
    a = _run(_signal(1), _bars(high={3: 106.5}))
    b = _run(_signal(1), _bars(high={3: 106.5}))
    assert a.trades.equals(b.trades)
    assert a.equity.equals(b.equity)


def test_a_signal_on_the_exit_bar_is_still_in_position() -> None:
    sig = pl.concat([_signal(1, at=T0), _signal(1, at=T0 + timedelta(minutes=10))])
    res = _run(sig, _bars(high={2: 120.0}))  # first trade exits inside bar 2
    assert res.trades.height == 1
    assert res.skipped["reason"].to_list() == ["IN_POSITION"]


def test_a_win_resets_the_consecutive_loss_counter() -> None:
    outcomes = ["L", "L", "W", "L", "L", "L"]
    low: dict[int, float] = {}
    high: dict[int, float] = {}
    for k, o in enumerate(outcomes):
        (low if o == "L" else high)[6 * k + 1] = 90.0 if o == "L" else 120.0
    sigs = pl.concat([_signal(1, at=T0 + timedelta(minutes=30 * k)) for k in range(6)])
    cfg = _cfg(limits=RiskLimits(daily_risk_budget_pct=10.0))
    res = _run(sigs, _bars(60, low=low, high=high), cfg)
    assert res.trades.height == 6  # never three losses in a row before the win resets the count


def test_short_floating_pnl_uses_the_ask_close() -> None:
    res = _run(_signal(-1), _bars(close={1: 99.0}, low={1: 98.9, 6: 80.0}))
    # short entry 99.97 ; floating at bar 1 marks against the ask close 99.0 + 0.20
    assert res.equity["equity"][1] == pytest.approx(100_000 + (99.97 - 99.20) * 1.66 * 100)


def test_short_target_needs_the_ask_not_just_the_bid() -> None:
    near = _run(_signal(-1), _bars(low={4: 93.8}))  # bid hits 93.8, ask 94.0 > target 93.97
    assert near.trades["exit_reason"][0] == "TIME"
    hit = _run(_signal(-1), _bars(low={4: 93.7}))  # ask 93.9 <= 93.97
    assert hit.trades["exit_reason"][0] == "TARGET"


def test_net_pnl_includes_swap() -> None:
    start = datetime(2026, 3, 2, 21, 50, tzinfo=UTC)
    cfg = _cfg(
        costs=CostModel(slippage_points=3.0, swap_long_points=-76.05, swap_short_points=-4.2)
    )
    t = run_backtest(_signal(1, at=start), _bars(start=start), cfg, PROFILE).trades.row(
        0, named=True
    )
    assert t["net_pnl"] == pytest.approx(t["gross_pnl"] - t["commission"] + t["swap"])
    assert t["swap"] < 0


def test_nan_and_inconsistent_bars_are_rejected_not_silently_ignored() -> None:
    nan_low = _bars(low={3: float("nan")})
    with pytest.raises(ValueError, match="finite"):
        _run(_signal(1), nan_low)
    with pytest.raises(ValueError, match="inconsistent"):
        _run(_signal(1), _bars(high={4: 99.0}))  # high below open/close/low
    with pytest.raises(ValueError, match="inconsistent"):
        _run(_signal(1), _bars(spread={2: -1.0}))
    with pytest.raises(ValueError, match="duplicate"):
        _run(_signal(1), _bars().vstack(_bars().head(1)).sort("timestamp"))


def test_missing_news_calendar_or_regime_fails_safe_by_default() -> None:
    strict = BacktestConfig(signal_timeframe=Timeframe.M5)
    with pytest.raises(ValueError, match="calendar"):
        run_backtest(_signal(1), _bars(), strict, PROFILE)
    with pytest.raises(ValueError, match="regime"):
        run_backtest(_signal(1).drop("regime"), _bars(), _cfg(), PROFILE)
    ok = run_backtest(
        _signal(1).drop("regime"), _bars(), _cfg(limits=RiskLimits(require_regime=False)), PROFILE
    )
    assert ok.trades.height == 1
    unknown = run_backtest(_signal(1, regime=None), _bars(), _cfg(), PROFILE)
    assert "REGIME_UNKNOWN" in unknown.skipped["reason"][0]


def test_calendar_blocks_entries_near_a_high_impact_event() -> None:
    cover = (T0 - timedelta(days=1), T0 + timedelta(days=1))
    cal = StaticCalendar(
        [NewsEvent(T0 + timedelta(minutes=5), "NFP", EventImpact.HIGH)], coverage=cover
    )
    cfg = _cfg(require_news_calendar=True, news_before_minutes=10, news_after_minutes=10)
    res = run_backtest(_signal(1), _bars(), cfg, PROFILE, calendar=cal)
    assert res.trades.height == 0
    assert "NEWS" in res.skipped["reason"][0]
    empty = StaticCalendar([], coverage=cover)
    assert run_backtest(_signal(1), _bars(), cfg, PROFILE, calendar=empty).trades.height == 1


def test_decision_times_in_other_time_zones_are_aligned_correctly() -> None:
    sig = _signal(1).with_columns(pl.col("decision_time").dt.convert_time_zone("Europe/Prague"))
    res = _run(sig, _bars())
    assert res.trades["entry_time"][0] == T0


def test_naive_decision_times_are_rejected() -> None:
    sig = _signal(1).with_columns(pl.col("decision_time").dt.replace_time_zone(None))
    with pytest.raises(ValueError, match="timezone"):
        _run(sig, _bars())


def test_risk_taken_by_a_trade_spanning_midnight_counts_for_the_entry_day() -> None:
    # Prague midnight = 23:00 UTC in winter. Trade 1 enters 22:50 and exits after midnight;
    # trade 2 on the new day must find a fresh daily risk budget.
    start = datetime(2026, 3, 2, 22, 50, tzinfo=UTC)
    sigs = pl.concat([_signal(1, at=start), _signal(1, at=start + timedelta(minutes=65))])
    cfg = _cfg(limits=RiskLimits(daily_risk_budget_pct=0.55))
    res = run_backtest(sigs, _bars(60, start=start), cfg, PROFILE)
    assert res.trades.height == 2


def test_weekend_rollovers_are_not_charged() -> None:
    friday = datetime(2026, 3, 6, 21, 0, tzinfo=UTC)  # 16:00 New York
    monday = datetime(2026, 3, 9, 10, 0, tzinfo=UTC)
    cm = CostModel()
    assert cm.rollover_nights(friday, monday) == 1  # only the Friday rollover
    assert (
        cm.rollover_nights(
            datetime(2026, 3, 4, 20, 0, tzinfo=UTC), datetime(2026, 3, 5, 20, 0, tzinfo=UTC)
        )
        == 1
    )
    assert cm.rollover_nights(monday, monday + timedelta(hours=2)) == 0


def test_intrabar_lows_are_kept_in_the_equity_low_curve() -> None:
    res = _run(_signal(1), _bars(low={1: 98.0}, high={5: 120.0}))
    eq = res.equity
    assert (eq["equity_low"] <= eq["equity"] + 1e-9).all()
    worst = 100_000 + (98.0 - 100.23) * 1.66 * 100
    assert eq["equity_low"][1] == pytest.approx(worst)
    assert eq["equity"][1] > eq["equity_low"][1]


def test_prop_breach_scan_uses_the_intrabar_low() -> None:
    ts = [T0 + timedelta(hours=i) for i in range(3)]
    frame = pl.DataFrame(
        {
            "timestamp": pl.Series(ts, dtype=pl.Datetime("us", "UTC")),
            "equity": [100_000.0, 99_900.0, 100_100.0],
            "equity_low": [100_000.0, 94_000.0, 100_000.0],
        }
    )
    assert prop_breaches(frame, PROFILE, initial_capital=100_000.0)["daily"] == [date(2026, 3, 2)]
    assert (
        prop_breaches(frame.drop("equity_low"), PROFILE, initial_capital=100_000.0)["daily"] == []
    )


def test_daily_risk_budget_accumulates_across_trades_on_the_same_day() -> None:
    sigs = pl.concat([_signal(1, at=T0), _signal(1, at=T0 + timedelta(minutes=30))])
    cfg = _cfg(limits=RiskLimits(daily_risk_budget_pct=0.55))
    res = _run(sigs, _bars(60, high={2: 120.0, 8: 120.0}), cfg)
    assert res.trades.height == 1
    assert "DAILY_RISK_BUDGET" in res.skipped["reason"][0]


def test_trades_record_the_regime_of_the_signal() -> None:
    res = _run(_signal(1, regime="TREND_UP"), _bars(high={3: 106.5}))
    assert res.trades["regime"][0] == "TREND_UP"
