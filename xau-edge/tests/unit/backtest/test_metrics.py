"""Backtest metrics (brief section 25) on hand-built trades and equity curves."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import polars as pl
import pytest

from xau_edge.backtest.metrics import compute_metrics, return_by_group

T0 = datetime(2026, 3, 2, 8, 0, tzinfo=UTC)


def _trades(raw: list[float], rs: list[float] | None = None) -> pl.DataFrame:
    pnls = [float(x) for x in raw]
    n = len(pnls)
    entry = [T0 + timedelta(days=i) for i in range(n)]
    return pl.DataFrame(
        {
            "entry_time": pl.Series(entry, dtype=pl.Datetime("us", "UTC")),
            "exit_time": pl.Series(
                [e + timedelta(hours=1) for e in entry], dtype=pl.Datetime("us", "UTC")
            ),
            "net_pnl": pnls,
            "net_r": rs if rs is not None else [p / 500.0 for p in pnls],
            "gross_pnl": pnls,
        }
    )


def _equity(values: list[float], step: timedelta = timedelta(days=1)) -> pl.DataFrame:
    ts = [T0 + step * i for i in range(len(values))]
    return pl.DataFrame(
        {"timestamp": pl.Series(ts, dtype=pl.Datetime("us", "UTC")), "equity": values}
    )


def test_basic_trade_statistics() -> None:
    m = compute_metrics(_trades([500, -250, 750, -250, 0.0]), _equity([100_000.0] * 6), 100_000.0)
    assert m.trade_count == 5
    assert m.net_profit == pytest.approx(750.0)
    assert m.win_rate == pytest.approx(2 / 5)
    assert m.avg_win == pytest.approx(625.0)
    assert m.avg_loss == pytest.approx(-250.0)
    assert m.expectancy == pytest.approx(150.0)
    assert m.avg_r == pytest.approx(150.0 / 500.0)
    assert m.profit_factor == pytest.approx(1250.0 / 500.0)


def test_longest_losing_streak_counts_consecutive_losses_only() -> None:
    m = compute_metrics(
        _trades([-1, -1, 5, -1, -1, -1, 2, -1]), _equity([100_000.0] * 9), 100_000.0
    )
    assert m.longest_losing_streak == 3
    flat = compute_metrics(_trades([-1, 0.0, -1]), _equity([100_000.0] * 4), 100_000.0)
    assert flat.longest_losing_streak == 1  # a break-even trade interrupts the streak


def test_profit_factor_is_undefined_without_losses_or_trades() -> None:
    assert compute_metrics(_trades([100, 200]), _equity([1e5] * 3), 1e5).profit_factor is None
    empty = compute_metrics(_trades([]), _equity([1e5] * 3), 1e5)
    assert empty.trade_count == 0
    assert empty.profit_factor is None
    assert empty.win_rate is None
    assert empty.expectancy is None


def test_max_drawdown_is_peak_to_trough_in_usd_and_fraction() -> None:
    eq = _equity([100_000.0, 110_000.0, 99_000.0, 105_000.0, 88_000.0, 120_000.0])
    m = compute_metrics(_trades([1.0]), eq, 100_000.0)
    assert m.max_drawdown == pytest.approx(22_000.0)  # 110,000 -> 88,000
    assert m.max_drawdown_pct == pytest.approx(0.2)
    assert m.net_return == pytest.approx(0.2)


def test_sharpe_and_sortino_from_daily_returns() -> None:
    eq = _equity([100_000.0, 101_000.0, 100_500.0, 102_000.0, 101_000.0, 103_000.0])
    m = compute_metrics(_trades([1.0]), eq, 100_000.0)
    rets = [
        101_000 / 100_000 - 1,
        100_500 / 101_000 - 1,
        102_000 / 100_500 - 1,
        101_000 / 102_000 - 1,
        103_000 / 101_000 - 1,
    ]
    mean = sum(rets) / len(rets)
    sd = (sum((r - mean) ** 2 for r in rets) / (len(rets) - 1)) ** 0.5
    assert m.sharpe == pytest.approx(mean / sd * 252**0.5)
    downside = (sum(min(r, 0) ** 2 for r in rets) / len(rets)) ** 0.5
    assert m.sortino == pytest.approx(mean / downside * 252**0.5)


def test_ratios_are_none_when_undefined() -> None:
    flat = compute_metrics(_trades([1.0]), _equity([100_000.0] * 5), 100_000.0)
    assert flat.sharpe is None
    assert flat.sortino is None
    assert flat.calmar is None
    rising = compute_metrics(
        _trades([1.0]), _equity([100_000.0, 101_000.0, 102_000.0, 103_000.0]), 100_000.0
    )
    assert rising.sortino is None  # no downside days
    assert rising.calmar is None  # no drawdown


def test_calmar_is_annualised_return_over_max_drawdown() -> None:
    values = [100_000.0, 110_000.0, 99_000.0] + [100_000.0 + 100 * i for i in range(1, 8)]
    eq = _equity(values)
    m = compute_metrics(_trades([1.0]), eq, 100_000.0)
    days = (eq["timestamp"][-1] - eq["timestamp"][0]).total_seconds() / 86_400
    expected = ((values[-1] / 100_000.0 - 1) * 365.0 / days) / m.max_drawdown_pct
    assert m.calmar == pytest.approx(expected)


def test_exposure_is_the_share_of_bars_inside_a_position() -> None:
    eq = _equity([1e5] * 10, step=timedelta(minutes=5))
    trades = pl.DataFrame(
        {
            "entry_time": pl.Series([T0 + timedelta(minutes=5)], dtype=pl.Datetime("us", "UTC")),
            "exit_time": pl.Series([T0 + timedelta(minutes=20)], dtype=pl.Datetime("us", "UTC")),
            "net_pnl": [10.0],
            "net_r": [0.1],
            "gross_pnl": [10.0],
        }
    )
    m = compute_metrics(trades, eq, 1e5)
    assert m.exposure == pytest.approx(4 / 10)  # bars at +5, +10, +15, +20 minutes


def test_return_by_group_sums_net_pnl_and_counts_trades() -> None:
    t = _trades([100, -40, 60, -10]).with_columns(
        pl.Series("session", ["LONDON", "LONDON", "NEW_YORK", "ASIA"])
    )
    out = return_by_group(t, "session")
    by = {r["session"]: r for r in out.iter_rows(named=True)}
    assert by["LONDON"]["net_pnl"] == pytest.approx(60.0)
    assert by["LONDON"]["trades"] == 2
    assert by["NEW_YORK"]["share_of_profit"] == pytest.approx(60 / 110)
    assert by["ASIA"]["mean_r"] == pytest.approx(-10 / 500)


def test_missing_columns_are_rejected() -> None:
    with pytest.raises(ValueError, match="column"):
        compute_metrics(_trades([1.0]).drop("net_r"), _equity([1e5] * 3), 1e5)
    with pytest.raises(ValueError, match="empty"):
        compute_metrics(_trades([1.0]), _equity([]), 1e5)
