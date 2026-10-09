from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from tests.unit.trading.helpers import SPEC, aligned_state, multi_tf, snap
from xau_edge.execution.override import OverridePolicy
from xau_edge.signals.schema import Direction, EvidenceStatus, NoTradeReason
from xau_edge.trading.adapter import to_legacy_signal
from xau_edge.trading.baseline import (
    STRATEGY_ID,
    BaselineConfig,
    DecisionContext,
    decide,
)
from xau_edge.trading.levels import (
    LevelConfig,
    StopModel,
    compute_stop,
    compute_targets,
)
from xau_edge.trading.market_state import build_market_state
from xau_edge.trading.schema import (
    EvidenceLabel,
    Refusal,
    TradeDecision,
    TradingSignal,
)
from xau_edge.trading.sizing import SymbolSpec, size_for_risk

CTX = DecisionContext(spec=SPEC, equity=100_000.0)


def refusal(signal: TradingSignal) -> set[Refusal]:
    return set(signal.refusal_reasons)


# -- BUY / SELL / WAIT chain ---------------------------------------------------------------


def test_an_aligned_bullish_state_gives_a_complete_buy() -> None:
    s = decide(aligned_state(), CTX)
    assert s.decision is TradeDecision.BUY
    assert s.evidence_status is EvidenceLabel.UNVALIDATED_BASELINE
    assert s.stop_loss is not None
    assert s.entry_price is not None
    assert s.take_profit is not None
    assert s.stop_loss < s.entry_price < s.take_profit
    assert s.risk_reward is not None
    assert s.risk_reward >= 1.5
    assert s.position_size is not None
    assert s.position_size > 0
    assert s.signal_expiry == s.timestamp + timedelta(minutes=15)
    assert s.volume_type == "TICK_VOLUME"
    assert any(r.startswith("H1:BULLISH") for r in s.reasons)


def test_the_sell_side_is_symmetric() -> None:
    state = aligned_state(
        h4_regime="TREND_DOWN",
        h1_trend="BEARISH",
        m30_structure="DOWN",
        m15_structure="DOWN",
        m15_pullback="PULLBACK_IN_DOWNTREND",
        m5_momentum="DOWN",
        m1_micro_state="ACTIVE_DOWN",
        distance_to_support=20.0,
        distance_to_resistance=3.0,
    )
    s = decide(state, CTX)
    assert s.decision is TradeDecision.SELL
    assert s.take_profit is not None
    assert s.entry_price is not None
    assert s.stop_loss is not None
    assert s.take_profit < s.entry_price < s.stop_loss


@pytest.mark.parametrize(
    ("over", "expected"),
    [
        ({"h1_trend": "NEUTRAL"}, Refusal.NO_DIRECTION),
        ({"h4_regime": "TREND_DOWN"}, Refusal.TIMEFRAME_CONFLICT),
        ({"m15_structure": "DOWN"}, Refusal.TIMEFRAME_CONFLICT),
        ({"m15_pullback": "NONE"}, Refusal.NO_SETUP),
        ({"m15_structure": "RANGE"}, Refusal.NO_SETUP),
        ({"m5_momentum": "FLAT"}, Refusal.NO_TRIGGER),
        ({"m1_micro_state": "ABNORMAL"}, Refusal.VOLATILITY_TOO_HIGH),
        ({"m1_micro_state": "QUIET"}, Refusal.VOLUME_TOO_LOW),
        ({"m1_micro_state": "ACTIVE_DOWN"}, Refusal.NO_TRIGGER),
        ({"execution_quality": "POOR"}, Refusal.SPREAD_TOO_WIDE),
        ({"execution_quality": "UNKNOWN"}, Refusal.UNKNOWN_STATE),
        ({"market_open": False}, Refusal.MARKET_CLOSED),
        ({"volatility_regime": "HIGH"}, Refusal.VOLATILITY_TOO_HIGH),
        ({"volatility_regime": "LOW"}, Refusal.VOLATILITY_TOO_LOW),
        ({"h4_regime": "SHOCK"}, Refusal.VOLATILITY_TOO_HIGH),
        ({"news_state": "BLOCKED"}, Refusal.NEWS_WINDOW),
        ({"news_state": "UNKNOWN"}, Refusal.NEWS_UNKNOWN),
        ({"data_quality": "STALE"}, Refusal.STALE_DATA),
        ({"data_quality": "UNKNOWN"}, Refusal.STALE_DATA),
        ({"available_timeframes": ("M5", "M15")}, Refusal.UNKNOWN_STATE),
        ({"distance_to_resistance": 1.0}, Refusal.TOO_CLOSE_TO_RESISTANCE),
    ],
)
def test_each_link_of_the_chain_refuses_with_its_own_reason(
    over: dict[str, object], expected: Refusal
) -> None:
    s = decide(aligned_state(**over), CTX)
    assert s.decision is TradeDecision.WAIT
    assert expected in refusal(s)
    assert s.entry_price is None
    assert s.stop_loss is None


def test_a_sell_too_close_to_support_is_refused() -> None:
    state = aligned_state(
        h1_trend="BEARISH",
        h4_regime="TREND_DOWN",
        m30_structure="DOWN",
        m15_structure="DOWN",
        m15_pullback="PULLBACK_IN_DOWNTREND",
        m5_momentum="DOWN",
        m1_micro_state="NEUTRAL",
        distance_to_support=0.5,
    )
    assert Refusal.TOO_CLOSE_TO_SUPPORT in refusal(decide(state, CTX))


def test_context_guards_block_with_their_reason() -> None:
    state = aligned_state()
    for field, reason in (
        ("broker_connected", Refusal.BROKER_DISCONNECTED),
        ("cooldown_active", Refusal.COOLDOWN),
        ("daily_limit_hit", Refusal.DAILY_LIMIT),
        ("risk_limit_hit", Refusal.RISK_LIMIT),
    ):
        value = field == "broker_connected"
        ctx = DecisionContext(spec=SPEC, equity=100_000.0, **{field: not value})  # type: ignore[arg-type]
        assert reason in refusal(decide(state, ctx)), field


def test_m1_may_block_but_never_reverses_the_h1_direction() -> None:
    bearish_m1 = aligned_state(m1_micro_state="ACTIVE_DOWN")
    s = decide(bearish_m1, CTX)
    assert s.decision is TradeDecision.WAIT  # blocked, never turned into a SELL
    unknown_m1 = aligned_state(m1_micro_state="UNKNOWN")
    assert decide(unknown_m1, CTX).decision is TradeDecision.BUY  # M1 is optional by default
    strict = BaselineConfig(require_m1=True)
    assert decide(unknown_m1, CTX, strict).decision is TradeDecision.WAIT


def test_the_decision_is_deterministic_and_the_id_is_stable() -> None:
    a = decide(aligned_state(), CTX)
    b = decide(aligned_state(), CTX)
    assert a == b
    assert a.signal_id == b.signal_id
    other = decide(aligned_state(price=2001.0), CTX)
    assert other.signal_id != a.signal_id


def test_a_wait_must_state_a_reason_and_a_trade_must_be_complete() -> None:
    s = decide(aligned_state(), CTX)
    wait_without_reason = {**s.model_dump(), "decision": TradeDecision.WAIT, "refusal_reasons": ()}
    with pytest.raises(ValidationError, match="refusal reason"):
        TradingSignal(**wait_without_reason)
    with pytest.raises(ValidationError, match="needs entry"):
        TradingSignal(**{**s.model_dump(), "stop_loss": None})
    with pytest.raises(ValidationError, match="BUY needs"):
        TradingSignal(**{**s.model_dump(), "stop_loss": s.take_profit})
    with pytest.raises(ValidationError, match="VALIDATED"):
        TradingSignal(**{**s.model_dump(), "evidence_status": EvidenceLabel.VALIDATED})


def test_the_baseline_never_displays_a_confidence_percentage() -> None:
    fields = set(TradingSignal.model_fields)
    assert not {"confidence", "probability", "win_probability"} & fields


# -- levels --------------------------------------------------------------------------------

CFG = LevelConfig()


def test_hybrid_stop_takes_the_larger_of_structure_and_atr_and_refuses_a_wide_one() -> None:
    atr = 2.0
    near = compute_stop(1, 2000.0, 1999.0, atr, CFG)  # structure 1.0+0.2 < 1.25*2
    assert near is not None
    assert near.distance == pytest.approx(2.5)
    far = compute_stop(1, 2000.0, 1996.0, atr, CFG)  # 4.0 + 0.2
    assert far is not None
    assert far.distance == pytest.approx(4.2)
    assert compute_stop(1, 2000.0, 1990.0, atr, CFG) is None  # 10.2 > 3*2
    sell = compute_stop(-1, 2000.0, 2004.0, atr, CFG)
    assert sell is not None
    assert sell.price > 2000.0


def test_stop_models_and_invalid_inputs() -> None:
    atr_only = compute_stop(1, 2000.0, None, 2.0, LevelConfig(stop_model=StopModel.ATR))
    assert atr_only is not None
    assert atr_only.model == "ATR"
    assert compute_stop(1, 2000.0, None, 2.0, LevelConfig(stop_model=StopModel.STRUCTURE)) is None
    assert compute_stop(1, 2000.0, 2001.0, 2.0, LevelConfig(stop_model=StopModel.STRUCTURE)) is None
    assert compute_stop(0, 2000.0, 1999.0, 2.0, CFG) is None
    assert compute_stop(1, 2000.0, 1999.0, 0.0, CFG) is None


def test_targets_are_r_multiples_capped_by_structure_and_judged_net_of_spread() -> None:
    stop = compute_stop(1, 2000.0, None, 2.0, CFG)
    assert stop is not None
    free = compute_targets(1, 2000.0, stop, CFG, spread=0.25, atr=2.0)
    assert free is not None
    assert free.tp1 == pytest.approx(2000.0 + 2.0 * stop.distance)
    assert free.net_rr < free.gross_rr  # the spread costs payoff
    assert free.required_win_rate == pytest.approx(1 / (1 + free.net_rr))
    assert free.tp2 is not None
    capped = compute_targets(1, 2000.0, stop, CFG, spread=0.25, atr=2.0, opposing_level=2005.0)
    assert capped is not None
    assert capped.capped_by_structure
    assert capped.tp1 < free.tp1
    assert capped.tp2 is None
    too_close = compute_targets(1, 2000.0, stop, CFG, spread=0.25, atr=2.0, opposing_level=2004.0)
    assert too_close is None  # room 3.8 < 1.5R after costs
    behind = compute_targets(1, 2000.0, stop, CFG, spread=0.25, atr=2.0, opposing_level=1999.0)
    assert behind is None
    huge_spread = compute_targets(1, 2000.0, stop, CFG, spread=3.0, atr=2.0)
    assert huge_spread is None


# -- sizing from the broker specification --------------------------------------------------


def test_lots_come_from_tick_value_and_round_down() -> None:
    # 10.0 price units at tick 0.01 / tick value 1.0 -> 1000 per lot; 0.25% of 100k = 250
    result = size_for_risk(100_000.0, 0.25, 2000.0, 1990.0, SPEC)
    assert result.allowed
    assert result.lots == pytest.approx(0.25)
    assert result.risk_amount == pytest.approx(250.0)
    odd = size_for_risk(100_000.0, 0.25, 2000.0, 1993.0, SPEC)  # 700 per lot -> 0.357 -> 0.35
    assert odd.lots == pytest.approx(0.35)
    assert odd.risk_pct_actual <= 0.25 + 1e-9


def test_the_contract_value_is_not_hard_coded() -> None:
    other = SymbolSpec(tick_value=0.5, volume_step=0.1, volume_min=0.1)
    assert size_for_risk(100_000.0, 0.25, 2000.0, 1990.0, other).lots == pytest.approx(0.5)


def test_sizing_refuses_instead_of_exceeding_the_risk() -> None:
    tiny = size_for_risk(1_000.0, 0.1, 2000.0, 1990.0, SPEC)  # budget 1, one lot loses 1000
    assert not tiny.allowed
    assert tiny.reasons == ("MIN_LOT_EXCEEDS_RISK",)
    close = SymbolSpec(stops_level_points=300)
    assert size_for_risk(100_000.0, 0.25, 2000.0, 1999.0, close).reasons == (
        "STOP_TOO_CLOSE_FOR_BROKER",
    )
    assert size_for_risk(float("nan"), 0.25, 2000.0, 1990.0, SPEC).reasons == ("INVALID_EQUITY",)
    assert size_for_risk(1e5, 5.0, 2000.0, 1990.0, SPEC).reasons == ("INVALID_RISK_PCT",)
    assert size_for_risk(1e5, 0.25, 2000.0, 2000.0, SPEC).reasons == ("INVALID_STOP",)
    capped = size_for_risk(1e8, 1.0, 2000.0, 1999.0, SymbolSpec(volume_max=5.0))
    assert capped.lots == pytest.approx(5.0)


def test_a_trade_sized_to_zero_becomes_a_wait_with_risk_limit() -> None:
    poor = DecisionContext(spec=SPEC, equity=500.0)
    s = decide(aligned_state(), poor)
    assert s.decision is TradeDecision.WAIT
    assert Refusal.RISK_LIMIT in refusal(s)


# -- adapter to the existing bridge --------------------------------------------------------


def test_a_baseline_buy_reaches_the_bridge_only_through_the_unvalidated_override() -> None:
    s = decide(aligned_state(), CTX)
    legacy = to_legacy_signal(s)
    assert legacy.direction is Direction.WAIT  # the evidence gate is untouched
    assert legacy.evidence_status is EvidenceStatus.NONE
    assert legacy.reasons == (NoTradeReason.NO_VALIDATED_EDGE,)
    assert legacy.candidate_direction is Direction.BUY
    assert legacy.stop_loss == s.stop_loss
    assert legacy.inputs_hash == s.signal_id
    off = OverridePolicy(enabled=False, strategy_id=STRATEGY_ID)
    assert off.permits(legacy, STRATEGY_ID) is None
    on = OverridePolicy(enabled=True, strategy_id=STRATEGY_ID)
    assert on.permits(legacy, STRATEGY_ID) is Direction.BUY
    assert on.permits(legacy, "some_other_strategy") is None


def test_a_wait_maps_to_a_wait_with_reasons_and_no_lean() -> None:
    s = decide(aligned_state(execution_quality="POOR", news_state="BLOCKED"), CTX)
    legacy = to_legacy_signal(s)
    assert legacy.direction is Direction.WAIT
    assert legacy.candidate_direction is None
    assert NoTradeReason.SPREAD_EXCESSIVE in legacy.reasons
    assert NoTradeReason.NEWS_RISK in legacy.reasons
    on = OverridePolicy(enabled=True, strategy_id=STRATEGY_ID)
    assert on.permits(legacy, STRATEGY_ID) is None


# -- the market state engine on synthetic multi-timeframe bars -----------------------------


def test_market_state_has_every_timeframe_and_labels_volume_as_tick_volume() -> None:
    bars = multi_tf(minutes=60 * 24 * 12)
    at = datetime(2026, 3, 12, 10, 37, tzinfo=UTC)
    state = build_market_state(bars, at, spread_points=25.0, news_state="CLEAR")
    assert set(state.available_timeframes) == {"M1", "M5", "M15", "M30", "H1", "H4"}
    assert state.volume_type == "TICK_VOLUME"
    assert state.data_quality == "OK"
    assert state.h1_trend in {"BULLISH", "BEARISH", "NEUTRAL"}
    assert state.price is not None
    assert state.snapshots["H1"].bar_closed <= at
    assert state.snapshots["M1"].bar_closed <= at
    assert state.atr_m15 is not None
    assert state.session != "UNKNOWN"


def test_market_state_ignores_bars_that_have_not_closed() -> None:
    full = multi_tf(minutes=60 * 24 * 12)
    at = datetime(2026, 3, 12, 10, 37, tzinfo=UTC)
    a = build_market_state(full, at, spread_points=25.0, news_state="CLEAR")
    b = build_market_state(full.truncated(at), at, spread_points=25.0, news_state="CLEAR")
    assert a == b  # the future cannot change the answer (live view equals research view)


def test_a_missing_or_stale_timeframe_degrades_the_state() -> None:
    bars = multi_tf(minutes=60 * 24 * 12)
    late = datetime(2026, 3, 20, 20, 0, tzinfo=UTC)  # long after the last bar
    stale = build_market_state(bars, late, spread_points=25.0, news_state="CLEAR")
    assert stale.data_quality in {"STALE", "UNKNOWN"}
    assert decide(stale, CTX).decision is TradeDecision.WAIT
    assert Refusal.STALE_DATA in refusal(decide(stale, CTX))
    only_m5 = bars.truncated(datetime(2026, 3, 12, 10, 37, tzinfo=UTC))
    reduced = type(only_m5)({k: v for k, v in only_m5.frames.items() if k.value in {"M5", "M15"}})
    state = build_market_state(
        reduced, datetime(2026, 3, 12, 10, 37, tzinfo=UTC), spread_points=25.0
    )
    assert state.h1_trend == "UNKNOWN"
    assert state.h4_regime == "UNKNOWN"
    assert Refusal.UNKNOWN_STATE in refusal(decide(state, CTX))


def test_snapshot_helper_is_a_valid_tf_snapshot() -> None:
    assert snap().timeframe == "M5"


def test_m30_is_context_only_it_never_vetoes_or_creates_a_trade() -> None:
    against = decide(aligned_state(m30_structure="DOWN"), CTX)
    assert against.decision is TradeDecision.BUY
    assert against.m30_state == "DOWN"  # still reported, just not a rule
    flat = decide(aligned_state(m30_structure="RANGE", h1_trend="NEUTRAL"), CTX)
    assert flat.decision is TradeDecision.WAIT


def test_unknown_news_is_allowed_for_paper_with_a_visible_warning_only() -> None:
    from xau_edge.trading.baseline import NEWS_NOT_VERIFIED  # noqa: PLC0415

    state = aligned_state(news_state="UNKNOWN")
    paper = decide(state, CTX, BaselineConfig(allow_unknown_news=True))
    assert paper.decision is TradeDecision.BUY
    assert NEWS_NOT_VERIFIED in paper.warnings
    assert paper.news_state == "UNKNOWN"  # never silently treated as clear
    assert decide(state, CTX).decision is TradeDecision.WAIT


def test_buy_enters_at_the_ask_and_sell_at_the_bid_when_a_quote_is_given() -> None:
    ctx = DecisionContext(spec=SPEC, equity=10_000.0, bid=1999.9, ask=2000.4)
    buy = decide(aligned_state(), ctx)
    assert buy.entry_price == pytest.approx(2000.4)
    assert (buy.bid, buy.ask) == (1999.9, 2000.4)
    sell = decide(
        aligned_state(
            h4_regime="TREND_DOWN", h1_trend="BEARISH", m30_structure="DOWN", m15_structure="DOWN",
            m15_pullback="PULLBACK_IN_DOWNTREND", m5_momentum="DOWN", m1_micro_state="ACTIVE_DOWN",
            distance_to_support=20.0, distance_to_resistance=20.0,
            recent_swing_high=2003.0, recent_swing_low=1990.0,
        ),
        ctx,
    )  # fmt: skip
    if sell.decision is TradeDecision.SELL:
        assert sell.entry_price == pytest.approx(1999.9)


def test_setup_id_is_stable_for_one_m5_trigger_and_changes_with_the_next() -> None:
    from tests.unit.trading.helpers import T0  # noqa: PLC0415

    first = snap("M5", bar_open=T0, bar_closed=T0 + timedelta(minutes=5))
    later = snap("M5", bar_open=T0 + timedelta(minutes=5), bar_closed=T0 + timedelta(minutes=10))
    a = decide(aligned_state(snapshots={"M5": first}), CTX)
    b = decide(
        aligned_state(
            snapshots={"M5": first}, timestamp=aligned_state().timestamp + timedelta(minutes=2)
        ),
        CTX,
    )
    c = decide(aligned_state(snapshots={"M5": later}), CTX)
    assert a.setup_id and a.setup_id == b.setup_id
    assert a.setup_id != c.setup_id
    assert a.signal_expiry == first.bar_closed + timedelta(
        minutes=15
    )  # anchored to the trigger bar


def test_a_stop_closer_than_the_broker_minimum_is_refused_with_its_own_reason() -> None:
    tight = SymbolSpec(stops_level_points=100_000)  # absurd minimum distance
    ctx = DecisionContext(spec=tight, equity=10_000.0)
    s = decide(aligned_state(), ctx)
    assert s.decision is TradeDecision.WAIT
    assert Refusal.INVALID_STOP_DISTANCE in s.refusal_reasons
