"""R:R, break-even, probability contract and the authorization state machine."""

from __future__ import annotations

import ast
import inspect
from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st
from pydantic import ValidationError

from xau_edge.decision_research import authorization, probability, rr
from xau_edge.decision_research.authorization import (
    PatternStage,
    Proposal,
    Thresholds,
    authorize,
)
from xau_edge.decision_research.probability import (
    CalibrationStatus,
    DecisionProbability,
    TradeSuccessProbability,
    publication_problems,
)
from xau_edge.decision_research.rr import (
    CostModel,
    break_even_probability,
    expected_value_r,
    net_payoff,
    required_probability,
)

pytestmark = pytest.mark.unit

COSTS = CostModel(
    spread=0.4,
    slippage=0.0,
    commission=0.0,
    swap=0.0,
    source="explicit test assumptions",
    verified=True,
)
FULL = Thresholds(
    min_sample=500,
    max_ci_width=0.12,
    calibration_margin=0.02,
    uncertainty_margin=0.03,
    min_ev_r=0.05,
    preregistration_ref="docs/research/v4/prereg-001.md",
)


def prob(
    side: str = "BUY",
    est: float = 0.60,
    n: int = 800,
    status: CalibrationStatus = CalibrationStatus.OOS_CALIBRATED,
) -> TradeSuccessProbability:
    return TradeSuccessProbability(
        side=side,
        estimate=est,
        ci_low=est - 0.04,
        ci_high=est + 0.04,
        sample_n=n,
        horizon_minutes=120,
        calibration_status=status,
        evidence_ref="study-x",
    )


def buy(stage: PatternStage = PatternStage.CONFIRMED, **kw: object) -> Proposal:
    base: dict[str, object] = {
        "side": "BUY",
        "stage": stage,
        "entry": 100.0,
        "tick_size": 0.01,
        "entry_causal": True,
        "stop_structurally_valid": True,
        "target_structurally_valid": True,
        "risk_ok": True,
        "stop": 98.0,
        "target": 105.0,
        "room_to_target": 9.0,
    }
    return Proposal(**{**base, **kw})


def sell(stage: PatternStage = PatternStage.CONFIRMED, **kw: object) -> Proposal:
    base: dict[str, object] = {
        "side": "SELL",
        "stage": stage,
        "entry": 100.0,
        "tick_size": 0.01,
        "entry_causal": True,
        "stop_structurally_valid": True,
        "target_structurally_valid": True,
        "risk_ok": True,
        "stop": 102.0,
        "target": 95.0,
        "room_to_target": 9.0,
    }
    return Proposal(**{**base, **kw})


def test_break_even_probability_follows_the_payoff_not_the_other_way_round() -> None:
    assert break_even_probability(1.0) == pytest.approx(0.5)
    assert break_even_probability(2.0) == pytest.approx(1 / 3)
    assert break_even_probability(3.0) == pytest.approx(0.25)
    with pytest.raises(ValueError, match="positive"):
        break_even_probability(0.0)
    # R:R 1:1 does not mean 50%: it only means 50% would be needed to break even
    assert break_even_probability(1.0) == 0.5 and expected_value_r(
        0.45, 1.0
    ) < 0 < expected_value_r(0.55, 1.0)


def test_costs_raise_the_probability_needed() -> None:
    free = net_payoff(
        "BUY",
        100.0,
        98.0,
        104.0,
        CostModel(
            spread=0.0,
            slippage=0.0,
            commission=0.0,
            swap=0.0,
            source="explicit zero costs",
            verified=True,
        ),
    )
    costly = net_payoff("BUY", 100.0, 98.0, 104.0, COSTS)
    assert free is not None and costly is not None
    assert free.net_rr == pytest.approx(2.0) == free.gross_rr
    assert costly.net_rr == pytest.approx(
        (4.0 - 0.4) / (2.0 + 0.4)
    )  # 1.5: below a 2R gross becomes 1.5 net
    assert costly.net_break_even_probability > costly.break_even_probability > 0.3


def test_a_gross_2r_can_be_a_net_failure() -> None:
    payoff = net_payoff(
        "BUY",
        100.0,
        99.0,
        102.0,
        CostModel(
            spread=0.5,
            slippage=0.2,
            commission=0.1,
            swap=0.0,
            source="test cost stress",
            verified=True,
        ),
    )
    assert payoff is not None and payoff.gross_rr == pytest.approx(2.0)
    assert payoff.net_rr < 2.0  # the rule uses the net figure


def test_levels_on_the_wrong_side_and_costs_larger_than_reward() -> None:
    assert net_payoff("BUY", 100.0, 101.0, 105.0, COSTS) is None  # stop above a long entry
    assert net_payoff("SELL", 100.0, 99.0, 95.0, COSTS) is None
    assert net_payoff("BUY", 100.0, 99.0, 95.0, COSTS) is None  # target below a long entry
    assert net_payoff("SELL", 100.0, 101.0, 105.0, COSTS) is None
    eaten = net_payoff("BUY", 100.0, 99.0, 100.3, COSTS)
    assert eaten is not None and eaten.net_rr == 0.0 and eaten.net_break_even_probability == 1.0


def test_required_probability_adds_the_preregistered_margins() -> None:
    assert required_probability(
        2.0, calibration_margin=0.02, uncertainty_margin=0.03
    ) == pytest.approx(1 / 3 + 0.05)
    with pytest.raises(ValueError, match="negative"):
        required_probability(2.0, calibration_margin=-0.01, uncertainty_margin=0.0)
    with pytest.raises(ValueError, match=r"\[0, 1\]"):
        expected_value_r(1.2, 2.0)
    assert expected_value_r(0.40, 2.0) == pytest.approx(0.4 * 2.0 - 0.6)  # 0.2R


def test_the_probability_contract_refuses_unsupported_numbers() -> None:
    with pytest.raises(ValidationError):  # no horizon
        TradeSuccessProbability(  # type: ignore[call-arg]
            side="BUY",
            estimate=0.6,
            ci_low=0.5,
            ci_high=0.7,
            sample_n=100,
            calibration_status=CalibrationStatus.OOS_CALIBRATED,
            evidence_ref="s",
        )
    with pytest.raises(ValidationError):  # estimate outside its own interval
        TradeSuccessProbability(
            side="BUY",
            estimate=0.9,
            ci_low=0.5,
            ci_high=0.7,
            sample_n=100,
            horizon_minutes=60,
            calibration_status=CalibrationStatus.OOS_CALIBRATED,
            evidence_ref="study",
        )
    empty = DecisionProbability()
    assert empty.buy_success is None and empty.sell_success is None
    assert empty.calibration_status is CalibrationStatus.UNVALIDATED


def test_publication_rule_needs_sample_interval_and_calibration() -> None:
    assert publication_problems(None, min_sample=500, max_ci_width=0.12) == [
        "PROBABILITY_UNAVAILABLE"
    ]
    assert publication_problems(prob(), min_sample=500, max_ci_width=0.12) == []
    assert "INSUFFICIENT_SAMPLE" in publication_problems(
        prob(n=40), min_sample=500, max_ci_width=0.12
    )
    assert "CALIBRATION_DEVELOPMENT" in publication_problems(
        prob(status=CalibrationStatus.DEVELOPMENT), min_sample=500, max_ci_width=0.12
    )
    assert "CONFIDENCE_INTERVAL_TOO_WIDE" in publication_problems(
        prob(), min_sample=500, max_ci_width=0.05
    )


def codes(auth: authorization.Authorization) -> list[str]:
    return [r.code for r in auth.reasons]


def test_today_everything_is_wait_because_no_probability_exists() -> None:
    result = authorize([buy(), sell(target=95.0)], COSTS, DecisionProbability(), Thresholds())
    assert result.action == "WAIT"
    assert set(codes(result)) <= {"NET_RR_BELOW_MIN", "THRESHOLDS_NOT_PREREGISTERED"}
    # a perfect-looking confirmed 2R pattern is still WAIT without evidence
    perfect = authorize([buy(target=106.0)], COSTS, DecisionProbability(), Thresholds())
    assert perfect.action == "WAIT" and codes(perfect) == ["THRESHOLDS_NOT_PREREGISTERED"]
    with_thresholds = authorize([buy(target=106.0)], COSTS, DecisionProbability(), FULL)
    assert with_thresholds.action == "WAIT" and codes(with_thresholds) == [
        "PROBABILITY_UNAVAILABLE"
    ]


@pytest.mark.parametrize(
    ("stage", "code"),
    [
        (PatternStage.NO_PATTERN, "NO_PATTERN"),
        (PatternStage.POSSIBLE, "PATTERN_POSSIBLE"),
        (PatternStage.DEVELOPING, "PATTERN_DEVELOPING"),
        (PatternStage.NEAR_CONFIRMATION, "PATTERN_NOT_CONFIRMED"),
        (PatternStage.INVALIDATED, "PATTERN_INVALIDATED"),
    ],
)
def test_a_pattern_that_is_not_confirmed_is_always_wait(stage: PatternStage, code: str) -> None:
    good = DecisionProbability(
        buy_success=prob(), calibration_status=CalibrationStatus.OOS_CALIBRATED
    )
    result = authorize([buy(stage, target=106.0)], COSTS, good, FULL)
    assert result.action == "WAIT" and codes(result) == [code]


def test_net_rr_below_floor_is_wait_and_says_the_number() -> None:
    result = authorize([buy(target=103.0)], COSTS, DecisionProbability(), FULL)
    assert result.action == "WAIT" and codes(result) == ["NET_RR_BELOW_MIN"]
    assert (
        "Net R:R hiện" in result.reasons[0].message
        and "dưới ngưỡng 1.5R" in result.reasons[0].message
    )
    assert result.net_rr["BUY"] < 2.0


def test_gross_160_after_costs_below_150_is_rejected() -> None:
    result = authorize(
        [buy(target=103.2)],
        CostModel(
            spread=0.05,
            slippage=0.05,
            commission=0.05,
            swap=0.05,
            source="predeclared synthetic cost-drop case",
            verified=True,
        ),
        DecisionProbability(),
        FULL,
    )
    assert result.action == "WAIT"
    assert codes(result) == ["NET_RR_BELOW_MIN"]
    assert result.net_rr["BUY"] < 1.5


def test_authorization_rounds_levels_adversely_before_net_rr() -> None:
    result = authorize(
        [buy(entry=100.001, stop=99.001, target=101.501, room_to_target=2.0)],
        CostModel(
            spread=0.0,
            slippage=0.0,
            commission=0.0,
            swap=0.0,
            source="explicit zero-cost rounding test",
            verified=True,
        ),
        DecisionProbability(),
        FULL,
    )
    assert result.net_rr["BUY"] == pytest.approx(1.4752475247524752)
    assert result.action == "WAIT" and codes(result) == ["NET_RR_BELOW_MIN"]


@pytest.mark.parametrize("spread", [0.01, 0.10, 0.25])
def test_spread_stress_is_applied_to_geometry(spread: float) -> None:
    result = authorize(
        [buy(target=103.2)],
        CostModel(
            spread=spread,
            slippage=0.0,
            commission=0.0,
            swap=0.0,
            source=f"predeclared spread stress {spread}",
            verified=True,
        ),
        DecisionProbability(),
        FULL,
    )
    if spread == 0.01:
        assert result.net_rr["BUY"] >= 1.5
    else:
        assert result.action == "WAIT" and result.net_rr["BUY"] < 1.5


def test_cost_values_and_cost_source_cannot_be_omitted() -> None:
    with pytest.raises(ValidationError):
        CostModel(spread=0.4)  # type: ignore[call-arg]
    with pytest.raises(ValidationError):
        CostModel(
            spread=0.4,
            slippage=0.0,
            commission=0.0,
            swap=0.0,
            source="missing verification flag",
        )  # type: ignore[call-arg]


def test_unverified_cost_model_never_authorizes() -> None:
    costs = CostModel(
        spread=0.0,
        slippage=0.0,
        commission=0.0,
        swap=0.0,
        source="unverified placeholder",
        verified=False,
    )
    result = authorize([buy(target=106.0)], costs, DecisionProbability(), FULL)
    assert result.action == "WAIT" and codes(result) == ["COST_MODEL_UNVERIFIED"]


@given(
    spread=st.integers(min_value=0, max_value=100),
    slippage=st.integers(min_value=0, max_value=50),
    commission=st.integers(min_value=0, max_value=50),
    swap=st.integers(min_value=0, max_value=50),
    extra_ticks=st.integers(min_value=0, max_value=500),
)
def test_property_no_authorized_candidate_below_net_rr_floor(
    spread: int, slippage: int, commission: int, swap: int, extra_ticks: int
) -> None:
    costs = CostModel(
        spread=spread / 100,
        slippage=slippage / 100,
        commission=commission / 100,
        swap=swap / 100,
        source="generated complete verified property-test model",
        verified=True,
    )
    reward = costs.total + 1.5 * (2.0 + costs.total) + extra_ticks / 100
    target = 100.0 + round(reward, 2)
    proposal = buy(target=target, room_to_target=target - 100.0)
    result = authorize(
        [proposal],
        costs,
        DecisionProbability(buy_success=prob(est=0.95)),
        FULL,
    )
    if result.action == "BUY_CANDIDATE":
        assert result.net_rr["BUY"] >= 1.5


def test_policy_floor_cannot_be_lowered_below_one_point_five() -> None:
    with pytest.raises(ValidationError):
        Thresholds(min_net_rr=1.49)


@pytest.mark.parametrize(
    ("field", "expected"),
    [
        ("entry_causal", "ENTRY_NOT_CAUSAL"),
        ("stop_structurally_valid", "INVALID_STOP"),
        ("target_structurally_valid", "INVALID_TARGET"),
        ("risk_ok", "RISK_GUARD"),
    ],
)
def test_missing_geometry_or_risk_gate_never_authorizes(field: str, expected: str) -> None:
    proposal = buy(target=106.0).model_copy(update={field: False})
    result = authorize([proposal], COSTS, DecisionProbability(), FULL)
    assert result.action == "WAIT" and codes(result) == [expected]


def test_structure_room_gate_rejects_an_unrealistic_target() -> None:
    probs = DecisionProbability(buy_success=prob())
    blocked = authorize([buy(target=106.0, room_to_target=3.0)], COSTS, probs, FULL)
    assert codes(blocked) == ["NO_ROOM_TO_TARGET"]
    unknown = authorize([buy(target=106.0, room_to_target=None)], COSTS, probs, FULL)
    assert codes(unknown) == ["NO_ROOM_TO_TARGET"]  # unknown room is not free room
    at_barrier = authorize([buy(target=106.0, room_to_target=6.0)], COSTS, probs, FULL)
    assert codes(at_barrier) == ["NO_ROOM_TO_TARGET"]  # target must remain one tick before it


def test_all_gates_pass_only_with_a_calibrated_probability_above_the_requirement() -> None:
    ok = authorize(
        [buy(target=106.0)], COSTS, DecisionProbability(buy_success=prob(est=0.60)), FULL
    )
    assert ok.action == "BUY_CANDIDATE" and ok.reasons == ()
    low = authorize(
        [buy(target=106.0)], COSTS, DecisionProbability(buy_success=prob(est=0.33)), FULL
    )
    assert codes(low) == ["PROBABILITY_BELOW_REQUIRED"]
    unvalidated = DecisionProbability(buy_success=prob(status=CalibrationStatus.DEVELOPMENT))
    assert codes(authorize([buy(target=106.0)], COSTS, unvalidated, FULL)) == [
        "CALIBRATION_DEVELOPMENT"
    ]
    few = DecisionProbability(buy_success=prob(n=30))
    assert codes(authorize([buy(target=106.0)], COSTS, few, FULL)) == ["INSUFFICIENT_SAMPLE"]


def test_positive_margin_is_not_enough_if_the_expected_value_is_below_the_threshold() -> None:
    thresholds = FULL.model_copy(update={"min_ev_r": 5.0})
    result = authorize(
        [buy(target=106.0)], COSTS, DecisionProbability(buy_success=prob(est=0.60)), thresholds
    )
    assert codes(result) == ["EV_NOT_POSITIVE"]


def test_sell_has_exactly_the_same_standards_as_buy() -> None:
    probs = DecisionProbability(sell_success=prob("SELL", 0.60))
    assert authorize([sell(target=94.0)], COSTS, probs, FULL).action == "SELL_CANDIDATE"
    assert codes(authorize([sell(target=97.0)], COSTS, probs, FULL)) == ["NET_RR_BELOW_MIN"]
    assert codes(authorize([sell(PatternStage.DEVELOPING, target=94.0)], COSTS, probs, FULL)) == [
        "PATTERN_DEVELOPING"
    ]


def test_conflicting_sides_are_wait_not_a_vote() -> None:
    probs = DecisionProbability(buy_success=prob("BUY", 0.60), sell_success=prob("SELL", 0.60))
    both = authorize([buy(target=106.0), sell(target=94.0)], COSTS, probs, FULL)
    assert both.action == "WAIT" and codes(both) == ["CONFLICT"]


def test_data_trouble_and_blockers_come_first() -> None:
    probs = DecisionProbability(buy_success=prob())
    assert codes(authorize([buy(target=106.0, data_ok=False)], COSTS, probs, FULL)) == [
        "DATA_NOT_TRUSTED"
    ]
    assert codes(authorize([buy(target=106.0, blockers=("NEWS",))], COSTS, probs, FULL)) == [
        "BLOCKED"
    ]
    assert codes(authorize([], COSTS, probs, FULL)) == ["NO_PROPOSAL"]
    assert codes(authorize([buy(entry=100.0, stop=101.0)], COSTS, probs, FULL)) == [
        "LEVELS_INVALID"
    ]


def test_incomplete_or_unreferenced_thresholds_never_authorize() -> None:
    probs = DecisionProbability(buy_success=prob())
    no_ref = FULL.model_copy(update={"preregistration_ref": None})
    assert codes(authorize([buy(target=106.0)], COSTS, probs, no_ref)) == [
        "THRESHOLDS_NOT_PREREGISTERED"
    ]
    assert Thresholds().min_net_rr == 1.5


def test_no_function_turns_a_shape_or_a_ratio_into_a_probability() -> None:
    """Static guard: the package exposes no callable returning a probability from geometry."""
    package = Path(rr.__file__).parent
    offenders: list[str] = []
    for path in package.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and not node.name.startswith("_"):
                ret = ast.unparse(node.returns) if node.returns else ""
                if (
                    "probab" in node.name.lower()
                    and ret in {"float", "float | None"}
                    and node.name
                    not in {
                        "break_even_probability",
                        "required_probability",
                    }
                ):  # these two are requirements derived from a payoff, not estimates
                    offenders.append(f"{path.name}:{node.name}")
    assert offenders == []
    assert "TradeEngine" not in inspect.getsource(authorization) + inspect.getsource(
        probability
    ).replace("TradeEngine, TradingSignal", "").replace("not wired to the TradeEngine", "")
