"""Risk engine: every refusal reason, sizing, kill switch, account validation."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from xau_edge.risk.engine import (
    AccountState,
    MarketState,
    RiskEngine,
    RiskLimits,
    TradeRequest,
)
from xau_edge.risk.kill_switch import KillSwitch
from xau_edge.risk.prop_rules import PropProfile

NOW = datetime(2026, 3, 3, 12, 0, tzinfo=UTC)
PROFILE = PropProfile(
    name="t",
    source="x",
    verified_on="2026-01-01",
    daily_loss_limit_pct=5.0,
    max_loss_limit_pct=10.0,
    max_loss_kind="static",
    internal_buffer_pct_of_limit=40.0,
)


def _account(**over: float | int) -> AccountState:
    base: dict[str, float | int] = {
        "initial_capital": 100_000.0,
        "balance": 100_000.0,
        "equity": 100_000.0,
        "day_start_balance": 100_000.0,
        "highest_eod_balance": 100_000.0,
        "open_positions": 0,
        "open_lots": 0.0,
        "risk_taken_today": 0.0,
        "consecutive_losses": 0,
    }
    base.update(over)
    return AccountState(timestamp=NOW, **base)


def _request(**over: float | str | None) -> TradeRequest:
    base: dict[str, float | str | None] = {"direction": 1, "stop_distance": 5.0}
    base.update(over)
    return TradeRequest(timestamp=NOW, **base)


def _market(**over: float | str | None) -> MarketState:
    base: dict[str, float | str | None] = {
        "spread_points": 30.0,
        "regime": "RANGE",
        "news_blocked": False,
    }
    base.update(over)
    return MarketState(**base)


def _engine(**limits: float | int) -> RiskEngine:
    return RiskEngine(RiskLimits(**limits), PROFILE)


def test_a_clean_request_is_allowed_with_the_sized_lots() -> None:
    d = _engine().evaluate(_request(), _account(), _market())
    assert d.allowed
    assert d.reasons == ()
    assert d.lots == pytest.approx(1.0)  # 0.5% of 100k = 500 ; stop 5.0 x 100 oz = 500 per lot
    assert d.risk_amount == pytest.approx(500.0)


@pytest.mark.parametrize(
    ("account", "market", "limits", "reason"),
    [
        ({"open_positions": 1}, {}, {}, "MAX_CONCURRENT"),
        ({"open_lots": 9.5}, {}, {"max_total_lots": 10.0}, "MAX_EXPOSURE"),
        ({"risk_taken_today": 1_000.0}, {}, {"daily_risk_budget_pct": 1.4}, "DAILY_RISK_BUDGET"),
        ({"consecutive_losses": 3}, {}, {"consecutive_loss_limit": 3}, "CONSECUTIVE_LOSSES"),
        ({}, {"spread_points": 150.0}, {"max_spread_points": 120.0}, "SPREAD"),
        ({}, {"regime": "SHOCK"}, {}, "VOLATILITY"),
        ({}, {"news_blocked": True}, {}, "NEWS"),
    ],
)
def test_each_guard_refuses_with_its_own_reason(
    account: dict[str, float],
    market: dict[str, float | str | bool],
    limits: dict[str, float],
    reason: str,
) -> None:
    d = _engine(**limits).evaluate(_request(), _account(**account), _market(**market))
    assert not d.allowed
    assert reason in d.reasons
    assert d.lots == 0.0


def test_guards_at_their_exact_limits_still_allow() -> None:
    d = _engine(max_spread_points=120.0).evaluate(
        _request(), _account(), _market(spread_points=120.0)
    )
    assert d.allowed
    d2 = _engine(consecutive_loss_limit=3).evaluate(
        _request(), _account(consecutive_losses=2), _market()
    )
    assert d2.allowed


def test_all_applicable_reasons_are_reported_together() -> None:
    d = _engine().evaluate(
        _request(),
        _account(open_positions=1, consecutive_losses=5),
        _market(spread_points=500.0, regime="SHOCK", news_blocked=True),
    )
    assert {"MAX_CONCURRENT", "CONSECUTIVE_LOSSES", "SPREAD", "VOLATILITY", "NEWS"} <= set(
        d.reasons
    )


def test_daily_loss_buffer_refuses_a_trade_whose_stop_would_eat_the_reserved_margin() -> None:
    # daily floor 95,000 ; buffer 40% of 5,000 = 2,000 -> equity - risk must stay >= 97,000
    ok = _engine().evaluate(
        _request(), _account(equity=97_600.0, day_start_balance=100_000.0), _market()
    )
    assert ok.allowed  # 97,600 - 500 = 97,100 >= 97,000
    d = _engine().evaluate(_request(), _account(equity=97_400.0), _market())
    assert not d.allowed
    assert "DAILY_LOSS_BUFFER" in d.reasons  # 97,400 - 500 = 96,900 < 97,000


def test_max_loss_buffer_uses_the_static_floor() -> None:
    # static floor 90,000 ; buffer 40% of 10,000 = 4,000 -> need equity - risk >= 94,000
    d = _engine().evaluate(
        _request(),
        _account(equity=94_400.0, balance=94_400.0, day_start_balance=94_400.0),
        _market(),
    )
    assert not d.allowed
    assert "MAX_LOSS_BUFFER" in d.reasons


def test_a_breached_account_trips_the_kill_switch_and_blocks_everything() -> None:
    engine = _engine()
    breached = _account(
        equity=94_900.0, day_start_balance=100_000.0
    )  # below the 95,000 daily floor
    assert engine.check_account(breached) is True
    assert engine.kill_switch.tripped
    assert "PROP_BREACH" in engine.kill_switch.reason
    d = engine.evaluate(_request(), _account(), _market())
    assert not d.allowed
    assert "KILL_SWITCH" in d.reasons


def test_kill_switch_stays_tripped_until_manually_reset() -> None:
    ks = KillSwitch()
    assert not ks.tripped
    ks.trip("manual test")
    ks.trip("second reason")
    assert ks.tripped
    assert ks.reason == "manual test"  # first reason is kept
    ks.reset(confirm="I understand the risk")
    assert not ks.tripped
    with pytest.raises(ValueError, match="confirm"):
        ks.reset(confirm="")


@pytest.mark.parametrize(
    "bad",
    [
        {"equity": float("nan")},
        {"equity": -5.0},
        {"balance": 0.0},
        {"initial_capital": 0.0},
        {"day_start_balance": float("inf")},
        {"open_lots": -1.0},
    ],
)
def test_invalid_account_state_is_refused_not_trusted(bad: dict[str, float]) -> None:
    d = _engine().evaluate(_request(), _account(**bad), _market())
    assert not d.allowed
    assert "ACCOUNT_STATE_INVALID" in d.reasons


def test_stop_too_wide_for_the_minimum_lot_is_refused() -> None:
    d = _engine().evaluate(_request(stop_distance=5_000.0), _account(), _market())
    assert not d.allowed
    assert "SIZE_TOO_SMALL" in d.reasons


def test_trailing_one_step_floor_tightens_after_profit() -> None:
    p = PropProfile(
        name="t",
        source="x",
        verified_on="2026-01-01",
        daily_loss_limit_pct=3.0,
        max_loss_limit_pct=10.0,
        max_loss_kind="trailing_end_of_day_balance",
        internal_buffer_pct_of_limit=0.0,
    )
    engine = RiskEngine(RiskLimits(), p)
    acct = _account(
        equity=98_500.0, balance=98_500.0, day_start_balance=98_500.0, highest_eod_balance=108_000.0
    )
    # trailing floor = 108,000 - 10,000 = 98,000 ; equity 98,500 - 500 risk = 98,000 -> allowed (>=)
    assert engine.evaluate(_request(), acct, _market()).allowed
    assert not engine.evaluate(
        _request(stop_distance=5.1), acct.model_copy(update={"equity": 98_400.0}), _market()
    ).allowed


def test_limits_validation() -> None:
    with pytest.raises(ValueError, match="risk_per_trade_pct"):
        RiskLimits(risk_per_trade_pct=0.0)
    with pytest.raises(ValueError, match="risk_per_trade_pct"):
        RiskLimits(risk_per_trade_pct=5.0)
    with pytest.raises(ValueError, match="max_concurrent_trades"):
        RiskLimits(max_concurrent_trades=0)


def test_exposure_limit_is_inclusive() -> None:
    # 9.0 open + 1.0 new = 10.0 == the limit: allowed ; 9.01 open: refused
    assert (
        _engine(max_total_lots=10.0)
        .evaluate(_request(), _account(open_lots=9.0), _market())
        .allowed
    )
    d = _engine(max_total_lots=10.0).evaluate(_request(), _account(open_lots=9.01), _market())
    assert "MAX_EXPOSURE" in d.reasons


def test_daily_buffer_boundary_counts_as_a_breach() -> None:
    # day start 102,500: floor 97,500 + buffer 2,000 = 99,500 ; equity 100,000 - risk 500 = 99,500.
    # Equality with a floor is a breach (T2.9), so exactly on the buffer line is refused.
    acct = _account(day_start_balance=102_500.0)
    assert "DAILY_LOSS_BUFFER" in _engine().evaluate(_request(), acct, _market()).reasons
    looser = _account(day_start_balance=102_499.0)
    assert _engine().evaluate(_request(), looser, _market()).allowed


def test_equity_exactly_on_a_floor_trips_the_kill_switch() -> None:
    engine = _engine()
    # static max-loss floor is 90,000 for a 100,000 account
    on_floor = _account(equity=90_000.0, balance=90_000.0, day_start_balance=90_000.0)
    assert engine.check_account(on_floor) is True
    daily = _engine()
    # daily floor = day start 100,000 - 5,000 = 95,000
    assert daily.check_account(_account(equity=95_000.0, day_start_balance=100_000.0)) is True
    just_above = _engine()
    assert just_above.check_account(_account(equity=95_000.01)) is False


def test_a_max_loss_breach_alone_trips_the_kill_switch() -> None:
    engine = _engine()
    # daily floor 84,900 is fine, but equity 89,500 is below the static max-loss floor 90,000
    acct = _account(equity=89_500.0, balance=89_900.0, day_start_balance=89_900.0)
    assert engine.check_account(acct) is True
    assert "PROP_BREACH" in engine.kill_switch.reason


@pytest.mark.parametrize("spread", [float("nan"), float("inf"), -5.0])
def test_unusable_spread_is_refused_not_waved_through(spread: float) -> None:
    d = _engine().evaluate(_request(), _account(), _market(spread_points=spread))
    assert not d.allowed
    assert "MARKET_STATE_INVALID" in d.reasons


def test_unknown_regime_is_refused_unless_explicitly_allowed() -> None:
    d = _engine().evaluate(_request(), _account(), _market(regime=None))
    assert not d.allowed
    assert "REGIME_UNKNOWN" in d.reasons
    ok = _engine(require_regime=False).evaluate(_request(), _account(), _market(regime=None))
    assert ok.allowed
