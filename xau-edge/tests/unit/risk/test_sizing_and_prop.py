"""Position sizing and prop-firm rule profiles."""

from __future__ import annotations

from pathlib import Path

import pytest

from xau_edge.risk.prop_rules import PropProfile, load_prop_profile
from xau_edge.risk.sizing import position_size

CONFIGS = Path(__file__).parents[3] / "configs" / "prop"


def test_size_is_risk_amount_over_stop_value_floored_to_the_lot_step() -> None:
    # risk 500 USD, stop 5.00 USD per oz, contract 100 oz -> 500 per lot of risk -> 1.00 lot
    assert position_size(100_000, 0.005, 5.0, contract_size=100) == pytest.approx(1.0)
    # 7.3 stop -> 0.6849 lot -> floored to 0.68
    assert position_size(100_000, 0.005, 7.3, contract_size=100) == pytest.approx(0.68)


def test_size_never_rounds_up_so_risk_never_exceeds_the_budget() -> None:
    for stop in (1.7, 3.3, 4.9, 6.1, 9.99):
        lots = position_size(100_000, 0.005, stop, contract_size=100)
        assert lots * stop * 100 <= 500.0 + 1e-9


def test_size_is_zero_below_the_minimum_lot_and_capped_at_the_maximum() -> None:
    assert position_size(900, 0.005, 5.0, contract_size=100) == 0.0  # 4.5 USD budget < 0.01 lot
    assert position_size(1_000, 0.005, 5.0, contract_size=100) == pytest.approx(0.01)
    assert position_size(1_000_000, 0.01, 0.5, contract_size=100, max_lot=50.0) == 50.0


def test_size_rejects_bad_inputs() -> None:
    for kwargs in (
        {"equity": 0.0, "risk_fraction": 0.005, "stop_distance": 5.0},
        {"equity": 1e5, "risk_fraction": 0.0, "stop_distance": 5.0},
        {"equity": 1e5, "risk_fraction": 0.5, "stop_distance": 5.0},
        {"equity": 1e5, "risk_fraction": 0.005, "stop_distance": 0.0},
        {"equity": float("nan"), "risk_fraction": 0.005, "stop_distance": 5.0},
    ):
        with pytest.raises(ValueError, match="must"):
            position_size(contract_size=100, **kwargs)


def test_shipped_ftmo_profiles_load_and_carry_their_provenance() -> None:
    two = load_prop_profile(CONFIGS / "ftmo_2step.yaml")
    one = load_prop_profile(CONFIGS / "ftmo_1step.yaml")
    assert (two.daily_loss_limit_pct, two.max_loss_limit_pct, two.max_loss_kind) == (
        5.0,
        10.0,
        "static",
    )
    assert (one.daily_loss_limit_pct, one.max_loss_limit_pct) == (3.0, 10.0)
    assert one.max_loss_kind == "trailing_end_of_day_balance"
    assert two.minimum_trading_days == 4
    assert two.verified_on.isoformat() == "2026-10-08"
    assert two.source.startswith("https://ftmo.com")
    assert two.ea_restrictions == "unverified"


def _profile(kind: str = "static") -> PropProfile:
    return PropProfile(
        name="t",
        source="x",
        verified_on="2026-01-01",
        daily_loss_limit_pct=5.0,
        max_loss_limit_pct=10.0,
        max_loss_kind=kind,
        internal_buffer_pct_of_limit=40.0,
    )


def test_daily_loss_floor_follows_the_ftmo_formula() -> None:
    p = _profile()
    assert p.daily_loss_floor(100_000, day_start_balance=100_000) == 95_000
    assert p.daily_loss_floor(100_000, day_start_balance=103_000) == 98_000
    assert p.daily_loss_amount(100_000) == 5_000


def test_max_loss_floor_static_and_trailing() -> None:
    assert _profile().max_loss_floor(100_000, highest_eod_balance=110_000) == 90_000
    trailing = _profile("trailing_end_of_day_balance")
    assert trailing.max_loss_floor(100_000, highest_eod_balance=100_000) == 90_000
    assert trailing.max_loss_floor(100_000, highest_eod_balance=108_000) == 98_000
    assert (
        trailing.max_loss_floor(100_000, highest_eod_balance=95_000) == 90_000
    )  # never below start


def test_profile_validation() -> None:
    with pytest.raises(ValueError, match="daily_loss_limit_pct"):
        PropProfile(
            name="t",
            source="x",
            verified_on="2026-01-01",
            daily_loss_limit_pct=0,
            max_loss_limit_pct=10.0,
            max_loss_kind="static",
        )
    with pytest.raises(ValueError, match="max_loss_kind"):
        _profile("weird")
