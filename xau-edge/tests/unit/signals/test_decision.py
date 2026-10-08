"""Decision layer: WAIT by default, every refusal reason, schema invariants, reproducibility."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from pydantic import ValidationError

from xau_edge.signals.decision import DecisionPolicy, SignalInputs, decide
from xau_edge.signals.schema import Direction, EvidenceStatus, NoTradeReason, Signal

T = datetime(2026, 3, 4, 14, 0, tzinfo=UTC)


def _inputs(**over: Any) -> SignalInputs:
    base: dict[str, Any] = {
        "timestamp": T,
        "price": 2000.0,
        "atr": 5.0,
        "spread_points": 30.0,
        "regime": "RANGE",
        "htf_bias": {"H4": 1, "H1": 1, "M15": 1, "M5": 1},
        "prob_up": 0.55,
        "prob_down": 0.20,
        "prob_neutral": 0.25,
        "probability_source": "analogues",
        "n_matches": 20,
        "similarity_quality": 0.6,
        "analogue_expected_r_long": 0.6,
        "analogue_expected_r_short": -0.3,
        "news_blocked": False,
        "evidence_status": EvidenceStatus.VALIDATED,
    }
    base.update(over)
    return SignalInputs(**base)


def test_all_checks_passing_with_validated_evidence_gives_a_consistent_buy() -> None:
    s = decide(_inputs())
    assert s.direction is Direction.BUY
    assert s.reasons == ()
    assert s.entry_zone is not None
    assert s.entry_zone[0] == pytest.approx(1999.5)
    assert s.entry_zone[1] == pytest.approx(2000.5)
    assert s.stop_loss == pytest.approx(1992.5)
    assert s.take_profit_1 == pytest.approx(2015.0)
    assert s.take_profit_2 == pytest.approx(2022.5)
    assert s.risk_reward == pytest.approx(2.0)
    assert s.expected_R == pytest.approx(0.6 - (30 + 6) * 0.01 / 7.5)
    assert s.entry_zone is not None
    assert s.stop_loss is not None
    assert s.take_profit_1 is not None
    assert s.take_profit_2 is not None
    assert s.stop_loss < s.entry_zone[0] <= s.entry_zone[1] < s.take_profit_1 < s.take_profit_2
    assert s.signal_expiry == T + timedelta(hours=1)
    assert s.inputs_hash


def test_a_sell_mirrors_the_buy() -> None:
    s = decide(
        _inputs(prob_up=0.2, prob_down=0.55, prob_neutral=0.25, htf_bias={"H4": -1, "H1": -1})
    )
    # short EV is -0.3 in the fixture: raise it so the check passes
    s = decide(
        _inputs(
            prob_up=0.2,
            prob_down=0.55,
            prob_neutral=0.25,
            htf_bias={"H4": -1, "H1": -1},
            analogue_expected_r_short=0.5,
        )
    )
    assert s.direction is Direction.SELL
    assert s.entry_zone is not None
    assert s.stop_loss is not None
    assert s.take_profit_1 is not None
    assert s.take_profit_2 is not None
    assert s.take_profit_2 < s.take_profit_1 < s.entry_zone[0] <= s.entry_zone[1] < s.stop_loss


def test_without_validated_evidence_the_answer_is_wait_but_the_lean_is_still_shown() -> None:
    s = decide(_inputs(evidence_status=EvidenceStatus.NONE))
    assert s.direction is Direction.WAIT
    assert s.candidate_direction is Direction.BUY
    assert NoTradeReason.NO_VALIDATED_EDGE in s.reasons
    assert s.prob_up == pytest.approx(0.55)
    assert any("WAIT because" in line for line in s.explanation)


@pytest.mark.parametrize(
    ("override", "reason"),
    [
        (
            {"prob_up": 0.40, "prob_down": 0.35, "prob_neutral": 0.25},
            NoTradeReason.EDGE_INSUFFICIENT,
        ),
        (
            {"prob_up": 0.38, "prob_down": 0.10, "prob_neutral": 0.52},
            NoTradeReason.EDGE_INSUFFICIENT,
        ),
        ({"analogue_expected_r_long": 0.04}, NoTradeReason.EV_NOT_POSITIVE),
        ({"analogue_expected_r_long": None}, NoTradeReason.MODEL_UNCERTAIN),
        ({"regime": "SHOCK"}, NoTradeReason.REGIME_UNSUPPORTED),
        ({"regime": None}, NoTradeReason.REGIME_UNSUPPORTED),
        ({"news_blocked": True}, NoTradeReason.NEWS_RISK),
        ({"news_blocked": None}, NoTradeReason.NEWS_UNKNOWN),
        ({"spread_points": 150.0}, NoTradeReason.SPREAD_EXCESSIVE),
        ({"data_valid": False}, NoTradeReason.DATA_INVALID),
        ({"prob_up": 0.7}, NoTradeReason.DATA_INVALID),  # probabilities no longer sum to one
        ({"atr": float("nan")}, NoTradeReason.DATA_INVALID),
        ({"prob_up": None}, NoTradeReason.DATA_INVALID),
        ({"n_matches": 5}, NoTradeReason.MODEL_UNCERTAIN),
        ({"similarity_quality": 0.95}, NoTradeReason.MODEL_UNCERTAIN),
        ({"similarity_quality": None}, NoTradeReason.MODEL_UNCERTAIN),
        ({"htf_bias": {"H4": -1, "H1": 1}}, NoTradeReason.HTF_BIAS_CONFLICT),
        ({"nearest_resistance": 2003.0}, NoTradeReason.ENTRY_QUALITY_POOR),
    ],
)
def test_each_check_refuses_with_its_own_reason(
    override: dict[str, Any], reason: NoTradeReason
) -> None:
    s = decide(_inputs(**override))
    assert s.direction is Direction.WAIT
    assert reason in s.reasons


def test_thresholds_are_inclusive_at_the_boundary() -> None:
    edge = decide(_inputs(prob_up=0.40, prob_down=0.25, prob_neutral=0.35))
    assert NoTradeReason.EDGE_INSUFFICIENT not in edge.reasons  # edge 0.15, p_up 0.40
    spread = decide(_inputs(spread_points=120.0))
    assert NoTradeReason.SPREAD_EXCESSIVE not in spread.reasons
    matches = decide(_inputs(n_matches=15))
    assert NoTradeReason.MODEL_UNCERTAIN not in matches.reasons
    clear = decide(_inputs(nearest_resistance=2005.0))  # exactly one ATR away
    assert NoTradeReason.ENTRY_QUALITY_POOR not in clear.reasons


def test_risk_reward_below_the_minimum_refuses() -> None:
    s = decide(_inputs(), DecisionPolicy(tp1_atr=2.0, stop_atr=1.5, tp2_atr=3.0))  # rr 1.33
    assert NoTradeReason.RISK_REWARD_POOR in s.reasons


def test_reasons_accumulate_and_are_unique() -> None:
    s = decide(
        _inputs(
            evidence_status=EvidenceStatus.NONE,
            regime="SHOCK",
            news_blocked=None,
            spread_points=400.0,
            n_matches=2,
        )
    )
    assert s.direction is Direction.WAIT
    assert {
        NoTradeReason.NO_VALIDATED_EDGE,
        NoTradeReason.REGIME_UNSUPPORTED,
        NoTradeReason.NEWS_UNKNOWN,
        NoTradeReason.SPREAD_EXCESSIVE,
        NoTradeReason.MODEL_UNCERTAIN,
    } <= set(s.reasons)
    assert len(s.reasons) == len(set(s.reasons))


def test_wait_is_a_complete_valid_output_with_an_explanation() -> None:
    s = decide(_inputs(evidence_status=EvidenceStatus.NONE))
    assert s.direction is Direction.WAIT
    text = " ".join(s.explanation)
    assert "H4 bullish" in text
    assert "Regime: RANGE" in text
    assert "analogues" in text
    assert "Expected value after costs" in text


def test_the_schema_itself_forbids_a_trade_with_refusals_or_without_evidence() -> None:
    good = decide(_inputs())
    with pytest.raises(ValidationError, match="no-trade reasons"):
        Signal(**{**good.model_dump(), "reasons": (NoTradeReason.NEWS_RISK,)})
    with pytest.raises(ValidationError, match="validated evidence"):
        Signal(**{**good.model_dump(), "evidence_status": EvidenceStatus.NONE})
    with pytest.raises(ValidationError, match="entry zone"):
        Signal(**{**good.model_dump(), "stop_loss": None})
    with pytest.raises(ValidationError, match="at least one reason"):
        Signal(**{**good.model_dump(), "direction": Direction.WAIT, "reasons": ()})


def test_same_inputs_give_the_identical_signal_and_hash() -> None:
    a = decide(_inputs(), code_version="abc")
    b = decide(_inputs(), code_version="abc")
    assert a == b
    assert a.inputs_hash == _inputs().digest()
    assert decide(_inputs(price=2001.0)).inputs_hash != a.inputs_hash


def test_a_buy_or_sell_never_appears_when_any_reason_exists() -> None:
    for override in ({"news_blocked": True}, {"spread_points": 999.0}, {"regime": "SHOCK"}):
        s = decide(_inputs(**override))
        assert s.direction is Direction.WAIT
        assert s.reasons


def test_a_sell_needs_the_minimum_probability_on_the_down_side() -> None:
    s = decide(
        _inputs(prob_up=0.15, prob_down=0.35, prob_neutral=0.50, analogue_expected_r_short=0.5)
    )
    assert s.candidate_direction is None
    assert NoTradeReason.EDGE_INSUFFICIENT in s.reasons


def test_zero_expected_value_is_refused_but_a_hair_above_is_allowed() -> None:
    pol = DecisionPolicy(slippage_points=0.0)
    zero = decide(_inputs(spread_points=0.0, analogue_expected_r_long=0.0), pol)
    assert NoTradeReason.EV_NOT_POSITIVE in zero.reasons
    above = decide(_inputs(spread_points=0.0, analogue_expected_r_long=0.001), pol)
    assert NoTradeReason.EV_NOT_POSITIVE not in above.reasons


def test_risk_reward_exactly_at_the_minimum_is_allowed() -> None:
    s = decide(_inputs(), DecisionPolicy(stop_atr=2.0, tp1_atr=3.0, tp2_atr=4.5))  # rr 1.5
    assert NoTradeReason.RISK_REWARD_POOR not in s.reasons


def test_similarity_exactly_at_the_limit_is_allowed() -> None:
    s = decide(_inputs(similarity_quality=0.8))
    assert NoTradeReason.MODEL_UNCERTAIN not in s.reasons


def test_either_higher_timeframe_conflict_refuses() -> None:
    h1_only = decide(_inputs(htf_bias={"H4": 0, "H1": -1}))
    h4_only = decide(_inputs(htf_bias={"H4": -1, "H1": 0}))
    assert NoTradeReason.HTF_BIAS_CONFLICT in h1_only.reasons
    assert NoTradeReason.HTF_BIAS_CONFLICT in h4_only.reasons


@pytest.mark.parametrize(
    "override",
    [
        {"analogue_expected_r_long": float("nan")},
        {"analogue_expected_r_long": float("inf")},
        {"similarity_quality": float("nan")},
        {"nearest_resistance": float("nan")},
        {"price": float("inf")},
        {"spread_points": float("nan")},
        {"analogue_mean_return": float("nan")},
    ],
)
def test_non_finite_inputs_never_produce_a_trade(override: dict[str, Any]) -> None:
    s = decide(_inputs(**override))
    assert s.direction is Direction.WAIT
    assert s.reasons


@pytest.mark.parametrize(
    "override",
    [
        {"htf_bias": {"H1": 1}},  # H4 missing
        {"htf_bias": {"H4": 1}},  # H1 missing
        {"htf_bias": {"H4": 5, "H1": 1}},
        {"htf_bias": {"H4": 1, "H1": 1, "X": -9}},
        {"regime": ""},
        {"regime": "shock"},
        {"regime": "CALM"},
        {"nearest_resistance": 1990.0},  # resistance below price: inconsistent
        {"nearest_support": 2010.0},  # support above price
        {"n_matches": -1},
    ],
)
def test_malformed_context_is_data_invalid_or_unsupported_never_a_trade(
    override: dict[str, Any],
) -> None:
    s = decide(_inputs(**override))
    assert s.direction is Direction.WAIT
    assert {NoTradeReason.DATA_INVALID, NoTradeReason.REGIME_UNSUPPORTED} & set(s.reasons)


def test_a_signal_cannot_be_turned_into_a_trade_by_copying_or_constructing() -> None:
    wait = decide(_inputs(evidence_status=EvidenceStatus.NONE))
    with pytest.raises(ValidationError):
        wait.model_copy(update={"direction": Direction.BUY})
    with pytest.raises((TypeError, ValidationError)):
        Signal.model_construct(**{**wait.model_dump(), "direction": Direction.SELL})
    ok = decide(_inputs())
    copy = ok.model_copy(update={"timestamp": T + timedelta(minutes=15)})  # harmless updates work
    assert copy.direction is Direction.BUY
