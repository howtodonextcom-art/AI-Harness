# ruff: noqa: E501
"""Cost ledger (unknown is never zero), the frozen executable fill, and the first-failure waterfall."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from xau_edge.decision_research.cost_ledger import (
    CostComponent,
    CostLedger,
    CostStatus,
    blocked_commission,
    blocked_slippage,
    default_ledger,
    measured_spread_price,
    spread_component,
    swap_component,
)
from xau_edge.decision_research.fill_model import (
    evidenced_spread_multiplier,
    next_bar_fill,
    tick_adverse,
)
from xau_edge.decision_research.waterfall import (
    ORDER,
    GateRecord,
    Stage,
    first_failure,
    raw_reasons,
    waterfall,
)

NOW = datetime(2026, 10, 11, 12, 0, tzinfo=UTC)


def verified(name: str, value: float, **kw: object) -> CostComponent:
    return CostComponent(
        name=name,
        value=value,
        source="test",
        measured_at=NOW,
        relevance="test",
        conversion="test",
        status=CostStatus.VERIFIED_MEASURED,
        **kw,
    )


# -- cost ledger ---------------------------------------------------------------------------------


def test_the_honest_ledger_is_blocked_by_slippage_and_commission_and_never_defaults_to_zero() -> (
    None
):
    ledger = default_ledger(2025, "LONDON", "BUY", 1, NOW)
    assert {b[0] for b in ledger.blockers(NOW)} == {"slippage", "commission"}
    assert ledger.gate_cost_model(NOW) is None
    assert all(b[1] == "BLOCKED_EXTERNALLY" for b in ledger.blockers(NOW))
    assert all(b[2] for b in ledger.blockers(NOW)), (
        "every blocker names the evidence that unblocks it"
    )


def test_a_ledger_with_all_four_verified_gives_a_verified_cost_model() -> None:
    ledger = CostLedger(
        components=(
            verified("spread", 0.3),
            verified("slippage", 0.1),
            verified("commission", 0.0),
            verified("swap", 0.7),
        )
    )
    model = ledger.gate_cost_model(NOW)
    assert model is not None and model.verified
    assert model.total == pytest.approx(1.1)


def test_a_verified_component_without_value_or_timestamp_cannot_exist() -> None:
    with pytest.raises(ValidationError):
        CostComponent(
            name="spread",
            value=None,
            source="s",
            measured_at=NOW,
            relevance="r",
            conversion="c",
            status=CostStatus.VERIFIED_MEASURED,
        )
    with pytest.raises(ValidationError):
        CostComponent(
            name="spread",
            value=0.2,
            source="s",
            measured_at=None,
            relevance="r",
            conversion="c",
            status=CostStatus.VERIFIED_BROKER_SPEC,
        )
    with pytest.raises(ValidationError):
        CostComponent(
            name="spread",
            value=0.2,
            source="s",
            measured_at=datetime.fromisoformat("2026-01-01T00:00:00"),
            relevance="r",
            conversion="c",
            status=CostStatus.VERIFIED_MEASURED,
        )


def test_a_blocked_component_must_say_what_would_unblock_it() -> None:
    with pytest.raises(ValidationError):
        CostComponent(
            name="slippage",
            value=None,
            source="s",
            relevance="r",
            conversion="c",
            status=CostStatus.BLOCKED_EXTERNALLY,
        )


def test_a_stale_swap_reading_reopens_the_gate() -> None:
    old = NOW - timedelta(days=30)
    ledger = CostLedger(
        components=(
            verified("spread", 0.3),
            verified("slippage", 0.1),
            verified("commission", 0.0),
            swap_component("BUY", 1, old),
        )
    )
    assert ledger.gate_cost_model(NOW) is None
    assert ledger.blockers(NOW)[0][:2] == ("swap", "STALE")
    assert ledger.gate_cost_model(old + timedelta(days=1)) is not None


def test_a_ledger_needs_exactly_the_four_components() -> None:
    with pytest.raises(ValidationError):
        CostLedger(components=(verified("spread", 0.3),))
    with pytest.raises(ValidationError):
        CostLedger(
            components=(
                verified("spread", 0.3),
                verified("spread", 0.3),
                blocked_slippage(),
                blocked_commission(),
            )
        )


def test_measured_spread_is_converted_to_price_and_a_missing_measurement_is_an_error() -> None:
    price, note = measured_spread_price(2025, "LONDON", "median")
    assert 0.1 < price < 0.5 and "n=" in note
    with pytest.raises(KeyError):
        measured_spread_price(2012, "LONDON")  # no tick history before 2021-10: never silently zero
    assert spread_component(2025, "LONDON").status is CostStatus.VERIFIED_MEASURED


def test_swap_direction_and_nights_scale_in_price_units() -> None:
    long1, long3 = swap_component("BUY", 1, NOW), swap_component("BUY", 3, NOW)
    short1 = swap_component("SELL", 1, NOW)
    assert long3.value == pytest.approx(3 * (long1.value or 0))
    assert (short1.value or 0) < (long1.value or 0)  # the broker's long swap is the expensive side


# -- executable fill ------------------------------------------------------------------------------


def test_the_fill_is_strictly_after_the_actionable_bar_and_never_uses_a_later_price() -> None:
    opens = [100.0, 101.0, 102.0, 103.0]
    spreads = [20.0, 20.0, 30.0, 20.0]
    fill = next_bar_fill("BUY", opens, spreads, 1, spread_multiplier=1.0)
    assert fill is not None and fill.bar_index == 2  # not bar 1 (the actionable close), not bar 3
    assert fill.price == pytest.approx(102.30)
    # changing any LATER bar cannot change the fill
    later = next_bar_fill(
        "BUY", [*opens[:3], 999.0], [*spreads[:3], 999.0], 1, spread_multiplier=1.0
    )
    assert later is not None and later.price == fill.price
    assert (
        next_bar_fill("BUY", opens, spreads, 3, spread_multiplier=1.0) is None
    )  # no bar after the last


def test_buy_pays_the_ask_and_sell_receives_the_bid_symmetrically() -> None:
    opens, spreads = [100.0, 100.0], [20.0, 20.0]
    buy = next_bar_fill("BUY", opens, spreads, 0, spread_multiplier=1.0)
    sell = next_bar_fill("SELL", opens, spreads, 0, spread_multiplier=1.0)
    assert buy is not None and sell is not None
    assert buy.price - sell.price == pytest.approx(0.20)  # exactly one spread apart
    assert sell.price == 100.0 and buy.basis != sell.basis


def test_tick_rounding_is_adverse_for_both_sides() -> None:
    assert tick_adverse(100.001, "BUY", 0.01) == pytest.approx(100.01)
    assert tick_adverse(100.009, "SELL", 0.01) == pytest.approx(100.00)


def test_an_unevidenced_spread_multiplier_makes_the_fill_unverified_not_free() -> None:
    fill = next_bar_fill("BUY", [100.0, 100.0], [20.0, 20.0], 0, spread_multiplier=None)
    assert fill is not None and not fill.verified and fill.unverified_reason
    assert fill.price > 100.0  # the recorded spread is still charged
    with pytest.raises(ValueError, match="never narrower"):
        next_bar_fill("BUY", [100.0, 100.0], [20.0, 20.0], 0, spread_multiplier=0.5)


def test_unusable_bar_data_gives_no_fill() -> None:
    assert (
        next_bar_fill("BUY", [100.0, float("nan")], [20.0, 20.0], 0, spread_multiplier=1.0) is None
    )
    assert next_bar_fill("BUY", [100.0, 100.0], [20.0, 0.0], 0, spread_multiplier=1.0) is None


def test_only_years_with_a_tick_comparison_have_an_evidenced_multiplier() -> None:
    assert (evidenced_spread_multiplier(2025) or 0) >= 1.0
    assert evidenced_spread_multiplier(2015) is None  # the development years: ticks do not exist


# -- waterfall ------------------------------------------------------------------------------------


def rec(**kw: object) -> GateRecord:
    base: dict[str, object] = {
        "family": "double_top_bottom",
        "pattern_id": "p",
        "valid_geometry": True,
        "room_ok": True,
        "gross_rr": 2.0,
        "fill_verified": True,
        "cost_verified": True,
        "net_rr": 1.8,
        "probability_available": True,
    }
    base.update(kw)
    return GateRecord(**base)


def test_the_order_is_the_documented_one() -> None:
    assert [s.value for s in ORDER] == [
        "INVALID_GEOMETRY", "ROOM_FAIL", "GROSS_RR_FAIL", "FILL_UNVERIFIED", "COST_UNVERIFIED",
        "NET_RR_FAIL", "PROBABILITY_UNAVAILABLE", "ENTRY_ELIGIBLE",
    ]  # fmt: skip


@pytest.mark.parametrize(
    ("kw", "expected"),
    [
        ({}, Stage.ENTRY_ELIGIBLE),
        ({"valid_geometry": False, "room_ok": False, "gross_rr": 0.4}, Stage.INVALID_GEOMETRY),
        ({"room_ok": False, "gross_rr": 0.4}, Stage.ROOM_FAIL),
        ({"room_ok": None}, Stage.ROOM_FAIL),  # unknown room is never free room
        ({"gross_rr": 1.49}, Stage.GROSS_RR_FAIL),
        ({"fill_verified": False, "cost_verified": False}, Stage.FILL_UNVERIFIED),
        ({"cost_verified": False}, Stage.COST_UNVERIFIED),
        ({"net_rr": 1.49}, Stage.NET_RR_FAIL),
        ({"net_rr": None}, Stage.NET_RR_FAIL),
        ({"probability_available": False}, Stage.PROBABILITY_UNAVAILABLE),
    ],
)
def test_each_record_gets_its_first_failing_gate(kw: dict[str, object], expected: Stage) -> None:
    assert first_failure(rec(**kw)) == expected


def test_the_floor_cannot_be_lowered_by_a_caller() -> None:
    assert first_failure(rec(gross_rr=1.2), min_rr=1.0) == Stage.GROSS_RR_FAIL
    assert first_failure(rec(net_rr=1.2), min_rr=0.0) == Stage.NET_RR_FAIL


def test_raw_reasons_overlap_while_the_partition_does_not() -> None:
    bad = rec(
        room_ok=False,
        gross_rr=1.0,
        fill_verified=False,
        cost_verified=False,
        net_rr=None,
        probability_available=False,
    )
    assert len(raw_reasons(bad)) == 6
    report = waterfall([bad, rec()])["ALL"]
    assert sum(report["first_failure"].values()) == report["detected"] == 2
    assert report["first_failure"]["ROOM_FAIL"] == 1
    assert report["first_failure"]["ENTRY_ELIGIBLE"] == 1


def test_survivors_never_increase_and_families_add_up_to_all() -> None:
    records = [
        rec(family="wolfe", pattern_id="a", gross_rr=3.0),
        rec(family="wolfe", pattern_id="b", room_ok=False),
        rec(family="double_top_bottom", pattern_id="c", gross_rr=0.7),
        rec(family="double_top_bottom", pattern_id="d", cost_verified=False),
    ]
    report = waterfall(records)
    assert report["ALL"]["detected"] == sum(
        report[f]["detected"] for f in ("wolfe", "double_top_bottom")
    )
    for family in report.values():
        surv = list(family["survivors"].values())
        assert surv == sorted(surv, reverse=True)
        assert sum(family["first_failure"].values()) == family["detected"]


# -- structure room -------------------------------------------------------------------------------

from xau_edge.decision_research.structure_room import nearest_barrier_gap, room_ok  # noqa: E402
from xau_edge.structure.pivots import Pivot  # noqa: E402


def test_a_pivot_confirmed_after_the_actionable_bar_is_the_future_and_is_ignored() -> None:
    pivots = [
        Pivot(bar=5, price=105.0, kind="H", confirmed_at=8),
        Pivot(bar=9, price=102.0, kind="H", confirmed_at=12),
    ]
    assert nearest_barrier_gap("BUY", 100.0, pivots, 10) == pytest.approx(
        5.0
    )  # the 102 high is not yet known
    assert nearest_barrier_gap("BUY", 100.0, pivots, 12) == pytest.approx(2.0)


def test_the_nearest_barrier_decides_and_duplicates_change_nothing() -> None:
    pivots = [
        Pivot(1, 110.0, "H", 4),
        Pivot(2, 104.0, "H", 5),
        Pivot(3, 104.0, "H", 6),
        Pivot(4, 99.0, "H", 7),
    ]
    assert nearest_barrier_gap("BUY", 100.0, pivots, 10) == pytest.approx(
        4.0
    )  # 99 is below the entry


def test_buy_and_sell_are_exact_mirrors() -> None:
    up = [Pivot(1, 104.0, "H", 4)]
    down = [Pivot(1, 96.0, "L", 4)]
    assert nearest_barrier_gap("BUY", 100.0, up, 10) == nearest_barrier_gap("SELL", 100.0, down, 10)
    assert nearest_barrier_gap("SELL", 100.0, up, 10) is None  # a swing high is not a SELL barrier


def test_the_target_must_stop_a_full_tick_before_the_barrier() -> None:
    assert room_ok(4.00, 3.99, 0.01) is True
    assert room_ok(4.00, 4.00, 0.01) is False  # touching the barrier is not room
    assert room_ok(4.00, 3.995, 0.01) is False  # needs reward + one tick
    assert room_ok(None, 1.0, 0.01) is None  # unknown room is never free room
