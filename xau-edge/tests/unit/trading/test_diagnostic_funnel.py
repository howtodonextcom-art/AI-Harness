"""The diagnostic funnel explains a WAIT without ever authorizing anything."""

from __future__ import annotations

from typing import Any

import pytest

from xau_edge.trading.funnel import diagnostic_from_signal
from xau_edge.trading.schema import Refusal, TradeDecision, TradingSignal


def _signal(
    refusals: tuple[Refusal, ...],
    *,
    h1: str = "BULLISH",
    h4: str = "RANGE",
    m15: str = "RANGE/NONE",
    m5: str = "FLAT",
    m1: str = "GOOD",
    decision: TradeDecision = TradeDecision.WAIT,
) -> TradingSignal:
    fields: dict[str, Any] = {
        "decision": decision,
        "refusal_reasons": refusals,
        "h1_bias": h1,
        "h4_bias": h4,
        "m15_setup": m15,
        "m5_trigger": m5,
        "m1_execution_state": m1,
        "spread_state": "GOOD",
        "volatility_regime": "NORMAL",
    }
    return TradingSignal.model_construct(**fields)


def _status(d: dict[str, Any], stage: str) -> str:
    return str(next(r["status"] for r in d["rows"] if r["stage"] == stage))


@pytest.mark.parametrize(
    ("refusal", "h1", "side"),
    [(Refusal.NO_SETUP, "BULLISH", "BUY"), (Refusal.NO_SETUP, "BEARISH", "SELL")],
)
def test_bias_stays_directional_while_action_waits(refusal: Refusal, h1: str, side: str) -> None:
    d = diagnostic_from_signal(_signal((refusal,), h1=h1))
    assert d["bias"]["side"] == side and d["action"] == "WAIT"
    assert _status(d, "H1 direction") == "PASS"
    assert _status(d, "M15 setup") == "FAIL"
    assert d["primary_blocker"] == "NO_SETUP"


def test_spread_block_still_judges_the_later_stages() -> None:
    d = diagnostic_from_signal(
        _signal((Refusal.SPREAD_TOO_WIDE, Refusal.VOLATILITY_TOO_LOW), m1="SPREAD_WIDE")
    )
    assert d["primary_stage"] == "Spread & regime"
    assert (
        _status(d, "H1 direction") == "PASS"
    )  # the screen no longer says "not reached" for a bullish H1
    assert _status(d, "M15 setup") == "FAIL" and _status(d, "M5 trigger") == "FAIL"
    assert _status(d, "M1 execution") == "FAIL"
    assert _status(d, "Trade plan") == "NOT_EVALUATED"
    assert {"M15 setup", "M5 trigger", "M1 execution"} <= set(d["also_missing"])
    assert d["required_passed"] < d["required_total"]


def test_no_trigger_with_a_valid_setup() -> None:
    d = diagnostic_from_signal(_signal((Refusal.NO_TRIGGER,), m15="UP/PULLBACK_IN_UPTREND"))
    assert _status(d, "M15 setup") == "PASS" and _status(d, "M5 trigger") == "FAIL"


def test_neutral_h1_leaves_the_directional_stages_unevaluated() -> None:
    d = diagnostic_from_signal(_signal((Refusal.NO_DIRECTION,), h1="NEUTRAL"))
    assert d["bias"]["side"] == "NEUTRAL"
    assert _status(d, "M15 setup") == "NOT_EVALUATED"


def test_h4_range_does_not_veto_but_a_strong_opposite_trend_does() -> None:
    ok = diagnostic_from_signal(_signal((Refusal.NO_SETUP,), h4="RANGE"))
    veto = diagnostic_from_signal(_signal((Refusal.TIMEFRAME_CONFLICT,), h4="TREND_DOWN"))
    assert _status(ok, "H4 / M15 alignment") == "PASS"
    assert _status(veto, "H4 / M15 alignment") == "FAIL"


def test_closed_market_judges_nothing_else() -> None:
    d = diagnostic_from_signal(_signal((Refusal.MARKET_CLOSED,)))
    assert _status(d, "Market & data") == "FAIL" and _status(d, "H1 direction") == "NOT_EVALUATED"


def test_ready_trade_passes_every_stage() -> None:
    d = diagnostic_from_signal(
        _signal((), m15="UP/PULLBACK_IN_UPTREND", m5="UP", decision=TradeDecision.BUY)
    )
    assert d["required_passed"] == d["required_total"] and d["primary_blocker"] is None


def test_formation_states_and_blockers() -> None:
    none = diagnostic_from_signal(_signal((Refusal.NO_SETUP,)))
    waiting = diagnostic_from_signal(_signal((Refusal.NO_TRIGGER,), m15="UP/PULLBACK_IN_UPTREND"))
    ready = diagnostic_from_signal(
        _signal((), m15="UP/PULLBACK_IN_UPTREND", m5="UP", decision=TradeDecision.BUY)
    )
    assert none["formation"]["state"] == "NO_SETUP"
    assert waiting["formation"]["state"] == "WAITING_TRIGGER"
    assert ready["formation"]["state"] == "READY"
    both = diagnostic_from_signal(_signal((Refusal.SPREAD_TOO_WIDE, Refusal.VOLATILITY_TOO_LOW)))
    assert both["blockers"] == ["SPREAD_TOO_WIDE", "VOLATILITY_TOO_LOW"]
    assert "tăng" in both["bias"]["reason"]


def test_an_armed_setup_is_forming_and_reports_its_age() -> None:
    sig = _signal((Refusal.NO_TRIGGER,), m15="UP/PULLBACK_IN_UPTREND")
    object.__setattr__(sig, "metadata", {"setup_phase": "ARMED", "setup_bars_since_armed": 2})
    d = diagnostic_from_signal(sig)
    assert d["formation"] == {"state": "FORMING", "bars_since_armed": 2}
