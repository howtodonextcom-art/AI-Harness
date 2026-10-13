"""Paper rules (pure): fills, bar management, PnL, swap, governor."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from xau_edge_v2.core import paper as p

T = datetime(2026, 3, 3, 10, 0, tzinfo=UTC)  # a Tuesday
POINT = 0.01


def test_entry_fill_is_adverse_for_both_sides() -> None:
    assert p.entry_fill("BUY", 2000.0, POINT) == pytest.approx(2000.03)
    assert p.entry_fill("SELL", 2000.0, POINT) == pytest.approx(1999.97)


@pytest.mark.parametrize(
    ("side", "high", "low", "spread", "expected", "price"),
    [
        ("BUY", 2003.0, 1996.5, 20, None, None),  # inside both levels
        ("BUY", 2003.0, 1994.9, 20, "STOP_LOSS", 1995.0 - 0.03),  # stop fills with slippage
        ("BUY", 2010.5, 1998.0, 20, "TAKE_PROFIT", 2010.0),  # target fills exactly
        # a SELL exits at the ask: the bar's spread moves its high/low up
        ("SELL", 2003.0, 1996.0, 20, None, None),
        ("SELL", 2004.9, 1996.0, 20, "STOP_LOSS", 2005.0 + 0.03),  # 2004.9 + 0.20 >= 2005
        ("SELL", 2003.0, 1989.9, 20, "TAKE_PROFIT", 1990.0),  # 1989.9 + 0.20 <= 1990.1? see below
    ],
)
def test_bar_evaluation(  # noqa: PLR0913, PLR0917 - a parametrised table row
    side: str, high: float, low: float, spread: float, expected: str | None, price: float | None
) -> None:
    sl, tp = (1995.0, 2010.0) if side == "BUY" else (2005.0, 1990.2)
    hit = p.evaluate_bar(side, sl, tp, high=high, low=low, spread_points=spread, point=POINT)  # type: ignore[arg-type]
    if expected is None:
        assert hit is None
        return
    assert hit is not None and hit.reason == expected
    if side == "SELL" and expected == "TAKE_PROFIT":
        assert hit.price == pytest.approx(1990.2)
    else:
        assert hit.price == pytest.approx(price)
    assert not hit.ambiguous


def test_a_bar_that_reaches_both_levels_takes_the_stop_and_says_so() -> None:
    hit = p.evaluate_bar(
        "BUY", 1995.0, 2010.0, high=2011.0, low=1994.0, spread_points=20, point=POINT
    )
    assert hit is not None and hit.reason == "STOP_LOSS" and hit.ambiguous
    sell = p.evaluate_bar(
        "SELL", 2005.0, 1990.0, high=2006.0, low=1989.0, spread_points=0, point=POINT
    )
    assert sell is not None and sell.reason == "STOP_LOSS" and sell.ambiguous


def test_spread_hurts_a_sell_stop_but_never_a_buy_stop() -> None:
    # bid high 2004.85 + 0.30 spread = 2005.15 >= 2005: the SELL stop is hit
    assert p.evaluate_bar(
        "SELL", 2005.0, 1990.0, high=2004.85, low=2000.0, spread_points=30, point=POINT
    )
    # a BUY stop is judged on the bid low alone
    assert (
        p.evaluate_bar(
            "BUY", 1995.0, 2010.0, high=2000.0, low=1995.05, spread_points=500, point=POINT
        )
        is None
    )


def test_pnl_uses_the_brokers_tick_values() -> None:
    assert p.pnl_usd("BUY", 2000.0, 2005.0, 0.1, 0.01, 1.0) == pytest.approx(50.0)  # 500 ticks
    assert p.pnl_usd("SELL", 2000.0, 2005.0, 0.1, 0.01, 1.0) == pytest.approx(-50.0)
    assert p.pnl_usd("BUY", 2000.0, 2005.0, 0.1, 0.01, 0.87) == pytest.approx(43.5)
    assert p.floating_pnl("BUY", 2000.0, 2003.0, 2003.4, 1.0, 0.01, 1.0) == pytest.approx(300.0)
    assert p.floating_pnl("SELL", 2000.0, 1997.0, 1997.4, 1.0, 0.01, 1.0) == pytest.approx(260.0)
    assert (
        p.close_price_at_quote("BUY", 1.0, 2.0) == 1.0
        and p.close_price_at_quote("SELL", 1.0, 2.0) == 2.0
    )


@pytest.mark.parametrize(
    ("opened", "closed", "nights"),
    [
        (datetime(2026, 3, 3, 10, tzinfo=UTC), datetime(2026, 3, 3, 15, tzinfo=UTC), 0),
        # Tue 13:00 NY (EST, 18:00 UTC) -> Wed 10:00 NY crosses one 17:00 roll
        (datetime(2026, 3, 3, 18, tzinfo=UTC), datetime(2026, 3, 4, 15, tzinfo=UTC), 1),
        # Fri 16:00 NY -> Mon 10:00 NY: only Friday 17:00 counts (no Saturday/Sunday roll)
        (datetime(2026, 3, 6, 21, tzinfo=UTC), datetime(2026, 3, 9, 15, tzinfo=UTC), 1),
        # a full week: Mon..Fri rolls = 5
        (datetime(2026, 3, 2, 10, tzinfo=UTC), datetime(2026, 3, 9, 10, tzinfo=UTC), 5),
    ],
)
def test_rollover_nights(opened: datetime, closed: datetime, nights: int) -> None:
    assert p.rollover_nights(opened, closed) == nights


def test_swap_is_assumed_per_night_and_signed() -> None:
    assert p.swap_usd("BUY", 1.0, 2, POINT, 100.0) == pytest.approx(-152.1)
    assert p.swap_usd("SELL", 1.0, 1, POINT, 100.0) == pytest.approx(-4.2)
    assert p.swap_usd("BUY", 1.0, 0, POINT, 100.0) == 0.0


CFG = p.GovernorConfig()


def check(  # noqa: PLR0913
    now: datetime = T,
    *,
    opens: list[p.OpenRecord] | None = None,
    today: list[p.OpenRecord] | None = None,
    closes: list[p.CloseRecord] | None = None,
    equity: float = 10_000.0,
    day_start: float = 10_000.0,
    risk: float = 0.25,
    session: str = "LONDON",
) -> list[str]:
    return p.governor_check(
        CFG, now, session, risk,
        opens=opens or [], opens_today=today if today is not None else (opens or []),
        closes=closes or [], day_start_equity=day_start, equity=equity,
    )  # fmt: skip


def rec(
    minutes_ago: float, *, closed: bool = True, session: str = "LONDON", risk: float = 0.25
) -> p.OpenRecord:
    return p.OpenRecord(T - timedelta(minutes=minutes_ago), session, risk, closed)


def test_governor_allows_a_clean_account() -> None:
    assert check() == []


def test_governor_daily_loss_stop() -> None:
    assert check(equity=9_799.0) == ["DAILY_LIMIT"]  # -2.01% >= 2%
    assert check(equity=9_801.0) == []
    assert p.flatten_required(CFG, 10_000.0, 9_649.0) and not p.flatten_required(
        CFG, 10_000.0, 9_651.0
    )
    assert p.daily_loss_pct(0.0, 5.0) == 0.0 and p.daily_loss_pct(10_000.0, 10_500.0) == 0.0


def test_governor_frequency_limits() -> None:
    opens = [rec(200), rec(100)]
    assert check(opens=opens) == []  # two trades, but over an hour apart for the older one
    assert check(opens=[rec(10), rec(20)]) == ["DAILY_LIMIT"]  # 2 within the hour
    six = [rec(300 + 10 * i, session=f"S{i}") for i in range(6)]
    assert "DAILY_LIMIT" in check(opens=six)  # 6 today
    three_same = [rec(100 + 100 * i) for i in range(3)]
    assert "DAILY_LIMIT" in check(opens=three_same, session="LONDON")  # 3 in this session
    assert check(opens=three_same, session="ASIA") == []


def test_governor_exposure_limits() -> None:
    assert check(opens=[rec(500, closed=False)]) == ["RISK_LIMIT"]  # one open already (max 1)
    assert "RISK_LIMIT" in check(risk=1.5)  # new risk above the 1% total cap


def test_governor_cooldowns() -> None:
    loss = [p.CloseRecord(T - timedelta(minutes=10), -50.0)]
    assert check(closes=loss) == ["COOLDOWN"]
    assert p.cooldown_until(T, loss, CFG) == T + timedelta(minutes=20)
    old = [p.CloseRecord(T - timedelta(minutes=45), -50.0)]
    assert check(closes=old) == [] and p.cooldown_until(T, old, CFG) is None
    win = [p.CloseRecord(T - timedelta(minutes=1), 50.0)]
    assert check(closes=win) == []
    streak = [p.CloseRecord(T - timedelta(minutes=300 - 40 * i), -10.0) for i in range(3)]
    assert p.loss_streak(streak) == 3
    assert "COOLDOWN" in check(closes=streak)  # 3 losses, last one 220 min ago (< 240)
    recent_streak = [p.CloseRecord(T - timedelta(minutes=100 - 40 * i), -10.0) for i in range(3)]
    assert "COOLDOWN" in check(closes=recent_streak)  # the longer streak cooldown (4 h) applies
    assert p.cooldown_until(T, recent_streak, CFG) == recent_streak[-1].closed_at + timedelta(
        minutes=240
    )
    assert p.loss_streak([p.CloseRecord(T, 5.0), p.CloseRecord(T, -1.0)]) == 1
