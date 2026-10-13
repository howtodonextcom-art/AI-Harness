"""Candidate V2 (core/candidate.py): parity with the control, each change, the guards, the invariants.

The plan used throughout is ``buy_state`` (price 2000, ATR(M15) 2.0, spread 25 points) with the control
context of test_core: BUY entry 2000.1 (the ask), stop 1995.80, net R:R about 1.84.
"""

from __future__ import annotations

import ast
import json
import random
from dataclasses import replace
from pathlib import Path

import pytest

from tests.unit.test_core import CTX, buy_state
from xau_edge_v2.core.candidate import (
    CORE_TIER,
    COST_CODE,
    COST_R_CAP,
    MEMORY_BARS,
    SHOCK_CODE,
    SPIKE_CODE,
    SPIKE_PERCENTILE,
    VARIANTS,
    CandidateConfig,
    Memory,
    Observation,
    candidate_step,
    config_for,
    cost_r,
)
from xau_edge_v2.core.decision import Decision, DecisionConfig, decide
from xau_edge_v2.core.market_state import MarketState

ROOT = Path(__file__).resolve().parents[2]
SPEC = json.loads((ROOT / "docs" / "research" / "cand_v2_spec.json").read_text(encoding="utf-8"))
OBS = Observation(m5_close=2000.0)


def sell_state(**kw: object) -> MarketState:
    return buy_state(
        h1_trend="BEARISH",
        h4_regime="TREND_DOWN",
        m15_structure="DOWN",
        m15_pullback="PULLBACK_IN_DOWNTREND",
        m5_momentum="DOWN",
        distance_to_support=20.0,
        distance_to_resistance=10.0,
        **kw,
    )


def run(
    variant: str,
    state: MarketState,
    mem: Memory | None = None,
    obs: Observation = OBS,
    bar: int = 0,
) -> tuple[Decision, Memory]:
    d, new_mem, _ = candidate_step(mem or Memory(), state, CTX, config_for(variant), obs, bar)
    return d, new_mem


# ---- the frozen spec and the code say the same thing ----
def test_variants_and_constants_equal_the_frozen_spec() -> None:
    spec_variants = {k: tuple(v) for k, v in SPEC["variants"].items() if not k.startswith("_")}
    assert spec_variants == VARIANTS
    assert SPEC["changes"]["C2"]["parameters"]["cost_R_cap"] == COST_R_CAP
    assert SPEC["changes"]["C1"]["parameters"]["memory_bars"] == MEMORY_BARS
    assert SPEC["definitions"]["spike_guard"].startswith(f"spread_percentile >= {SPIKE_PERCENTILE}")
    assert SPEC["definitions"]["lifecycle"]["memory_bars"] == MEMORY_BARS
    assert SPEC["candidate"]["strategy_version"] == "2.0.0-cand.1"
    assert all(v in CORE_TIER for v in VARIANTS if not v.startswith("X_"))
    assert "X_C7" not in CORE_TIER and "X_CORE_C7" not in CORE_TIER


def test_the_invariants_are_the_controls() -> None:
    from xau_edge_v2.core import risk  # noqa: PLC0415

    inv = SPEC["invariants"]
    assert (inv["MIN_NET_RR"], inv["R_MULTIPLE"], inv["ATR_K"], inv["MAX_STOP_ATR"]) == (
        risk.MIN_NET_RR,
        risk.R_MULTIPLE,
        risk.ATR_K,
        risk.MAX_STOP_ATR,
    )
    assert inv["risk_pct_per_trade"] == DecisionConfig().risk_pct


# ---- parity: every flag off is the control, bit for bit ----
def _random_state(rng: random.Random, sell: bool) -> MarketState:
    """Mostly coherent chains (each field takes its supportive value with probability 0.8)."""
    up, down = ("DOWN", "UP") if sell else ("UP", "DOWN")

    def pick(good: object, others: list[object]) -> object:
        return good if rng.random() < 0.8 else rng.choice(others)

    kw: dict[str, object] = {
        "h4_regime": pick(
            "TREND_DOWN" if sell else "TREND_UP",
            ["TREND_UP", "TREND_DOWN", "RANGE", "SHOCK", "HIGH_VOLATILITY"],
        ),
        "m15_structure": pick(up, [down, "RANGE", "REVERSAL_UP", "REVERSAL_DOWN"]),
        "m15_pullback": pick(
            "PULLBACK_IN_DOWNTREND" if sell else "PULLBACK_IN_UPTREND",
            ["NONE", "PULLBACK_IN_UPTREND"],
        ),
        "m5_momentum": pick(up, [down, "FLAT"]),
        "m1_micro_state": pick("NEUTRAL", ["QUIET", "ACTIVE_UP", "ACTIVE_DOWN", "ABNORMAL"]),
        "volatility_regime": pick("NORMAL", ["LOW", "HIGH"]),
        "execution_quality": pick("GOOD", ["POOR", "UNKNOWN"]),
        "spread": rng.choice([5.0, 25.0, 60.0, 200.0]),
        "spread_percentile": rng.choice([0.1, 0.5, 0.95, 0.995]),
        "distance_to_resistance": rng.choice([0.5, 5.0, 12.0, 30.0, None]),
        "distance_to_support": rng.choice([0.5, 5.0, 12.0, 30.0, None]),
        "h1_trend": "BEARISH" if sell else "BULLISH",
    }
    return buy_state(**kw)


def test_all_flags_off_is_the_control_exactly() -> None:
    rng = random.Random(11)
    signals = 0
    for i in range(1500):
        state = _random_state(rng, sell=bool(i % 2))
        d, _, _ = candidate_step(Memory(), state, CTX, CandidateConfig(), OBS, i)
        c = decide(state, CTX)
        assert d == c
        signals += c.action != "WAIT"
    assert signals > 50  # the comparison is not vacuous


# ---- C2: the cost gate ----
WIDE_BUT_CHEAP = {"execution_quality": "POOR", "spread": 50.0, "spread_percentile": 0.95}


def test_c2_prices_cost_against_risk_not_against_five_minute_noise() -> None:
    state = buy_state(**WIDE_BUT_CHEAP, spread_to_atr_m5=0.4)
    control = decide(state, CTX)
    assert control.action == "WAIT" and "SPREAD_TOO_WIDE" in control.refusals
    d, _ = run("A_C2", state)
    assert d.action == "BUY"
    ratio = cost_r(d, state.spread)
    assert ratio is not None and ratio <= COST_R_CAP
    assert ratio == pytest.approx((50.0 * 0.01 + 6 * 0.01) / abs(d.entry_price - d.stop_loss))  # type: ignore[operator]


def test_c2_refuses_when_cost_is_a_large_share_of_the_risk() -> None:
    state = buy_state(spread=80.0, execution_quality="GOOD", spread_percentile=0.5)
    d, _ = run("A_C2", state)
    assert d.action == "WAIT" and d.refusals == (COST_CODE,)
    assert d.entry_price is None and d.lots is None  # no level survives a veto


def test_c2_spike_guard_and_unknown_spread_still_refuse() -> None:
    spike = buy_state(execution_quality="POOR", spread_percentile=0.995)
    d, _ = run("A_C2", spike)
    assert d.action == "WAIT" and "SPREAD_TOO_WIDE" in d.refusals
    unknown = buy_state(execution_quality="UNKNOWN", spread=None, spread_percentile=None)
    d2, _ = run("A_C2", unknown)
    assert d2.action == "WAIT" and "UNKNOWN_STATE" in d2.refusals
    assert SPIKE_CODE == "SPREAD_SPIKE"  # named in the spec's guard list


def test_c2_keeps_the_m1_abnormal_block() -> None:
    state = buy_state(execution_quality="POOR", m1_micro_state="ABNORMAL", spread_percentile=0.5)
    d, _ = run("A_C2", state)
    assert d.action == "WAIT" and "VOLATILITY_TOO_HIGH" in d.refusals


# ---- C3a / C3b ----
def test_c3a_drops_only_the_low_volatility_gate() -> None:
    low = buy_state(volatility_regime="LOW")
    assert decide(low, CTX).action == "WAIT"
    assert run("A_C3a", low)[0].action == "BUY"
    assert run("A_C3a", buy_state(volatility_regime="HIGH"))[0].action == "WAIT"


def test_c3b_replaces_the_high_gate_by_the_shock_guard() -> None:
    high = buy_state(volatility_regime="HIGH", h4_regime="HIGH_VOLATILITY")
    assert decide(high, CTX).action == "WAIT"
    d, _ = run("A_C3b", high)
    assert d.action == "BUY"
    shock = Observation(shock=True, m5_close=2000.0)
    d2, _ = run("A_C3b", high, obs=shock)
    assert d2.action == "WAIT" and d2.refusals == (SHOCK_CODE,)
    assert (
        run("A_C3b", buy_state(h4_regime="SHOCK"))[0].action == "WAIT"
    )  # the H4 SHOCK block stays


def test_the_shock_guard_belongs_to_c3b_only() -> None:
    shock = Observation(shock=True, m5_close=2000.0)
    assert run("A_C3a", buy_state(), obs=shock)[0].action == "BUY"
    assert run("A_C3b", buy_state(), obs=shock)[0].action == "WAIT"


# ---- C1: the lifecycle ----
LATER = {
    "m15_pullback": "NONE",
    "m15_structure": "UP",
}  # the pullback has ended: the control says NO_SETUP


def test_c1_remembers_a_setup_across_the_trigger() -> None:
    armed = buy_state(m5_momentum="FLAT")
    d0, mem = run("A_C1", armed, bar=0)
    assert d0.action == "WAIT" and mem.side == "BUY" and mem.arm_bar == 0
    later = buy_state(**LATER)
    assert decide(later, CTX).refusals == ("NO_SETUP",)
    d1, mem1 = run("A_C1", later, mem, bar=3)
    assert d1.action == "BUY" and mem1.last_armed_bar == 0


def test_c1_memory_expires_after_six_bars() -> None:
    _, mem = run("A_C1", buy_state(m5_momentum="FLAT"), bar=0)
    later = buy_state(**LATER)
    assert run("A_C1", later, mem, bar=MEMORY_BARS)[0].action == "BUY"
    d, mem2 = run("A_C1", later, mem, bar=MEMORY_BARS + 1)
    assert d.action == "WAIT" and mem2.side is None


@pytest.mark.parametrize(
    ("change", "obs", "why"),
    [
        ({"h1_trend": "NEUTRAL"}, OBS, "H1_BIAS"),
        ({"h1_trend": "BEARISH"}, OBS, "H1_BIAS"),
        ({"h4_regime": "TREND_DOWN"}, OBS, "H4_VETO"),
        ({"m15_structure": "DOWN"}, OBS, "M15_AGAINST"),
        ({"m15_structure": "REVERSAL_DOWN"}, OBS, "M15_AGAINST"),
        ({}, Observation(shock=True, m5_close=2000.0), "SHOCK"),
        ({}, Observation(m5_close=1990.0), "STOP_LEVEL"),
        ({"data_quality": "STALE"}, OBS, "DATA"),
        ({"market_open": False}, OBS, "DATA"),
    ],
)
def test_c1_invalidation(change: dict[str, object], obs: Observation, why: str) -> None:
    _, mem = run("A_C1", buy_state(m5_momentum="FLAT"), bar=0)
    assert mem.planned_stop is not None and mem.planned_stop < 2000.0
    later = buy_state(**{**LATER, **change})
    _, new_mem, info = candidate_step(mem, later, CTX, config_for("A_C1"), obs, 2)
    assert info.invalidated_by == why
    assert new_mem.side is None or info.lifecycle == "ARMED"  # only a fresh arming can follow


def test_c1_is_off_without_the_flag() -> None:
    _, mem = run("A_C2", buy_state(m5_momentum="FLAT"), bar=0)
    assert mem == Memory()
    assert run("A_C2", buy_state(**LATER), mem, bar=2)[0].action == "WAIT"


def test_c1_never_replays_a_stale_memory_against_the_current_bias() -> None:
    _, mem = run("A_C1", buy_state(m5_momentum="FLAT"), bar=0)
    d, _ = run("A_C1", replace(sell_state(), **LATER), mem, bar=2)
    assert d.action != "BUY"


# ---- C7 (exploratory) ----
def test_c7_uses_higher_timeframe_levels_for_the_room() -> None:
    near = buy_state(distance_to_resistance=1.0)
    assert decide(near, CTX).refusals == ("TOO_CLOSE_TO_RESISTANCE",)
    assert (
        run("X_C7", near, obs=Observation(m5_close=2000.0, h1_resistance=2040.0))[0].action == "BUY"
    )
    blocked = Observation(m5_close=2000.0, h1_resistance=2001.0)
    assert run("X_C7", buy_state(), obs=blocked)[0].action == "WAIT"


# ---- symmetry, direction, determinism, invariants ----
@pytest.mark.parametrize("variant", sorted(VARIANTS))
def test_buy_and_sell_mirror_under_every_variant(variant: str) -> None:
    obs = Observation(m5_close=2000.0, h1_resistance=2050.0, h1_support=1950.0)
    b, _ = run(variant, buy_state(), obs=obs)
    s, _ = run(variant, sell_state(), obs=obs)
    assert (b.action, s.action) in {("BUY", "SELL"), ("WAIT", "WAIT")}


def test_the_candidate_never_trades_against_the_h1_bias_or_breaks_an_invariant() -> None:
    rng = random.Random(5)
    seen = 0
    for variant in ("CORE", "LOO_noC1", "LOO_noC2", "X_CORE_C7"):
        cfg = config_for(variant)
        mem = Memory()
        for bar in range(600):
            state = _random_state(rng, sell=rng.random() < 0.5)
            obs = Observation(
                shock=rng.random() < 0.1,
                h1_resistance=rng.choice([None, 2003.0, 2060.0]),
                h1_support=rng.choice([None, 1940.0, 1997.0]),
                m5_close=2000.0 + rng.uniform(-6, 6),
            )
            d, mem, _ = candidate_step(mem, state, CTX, cfg, obs, bar)
            if d.action == "WAIT":
                continue
            seen += 1
            assert d.action == {"BULLISH": "BUY", "BEARISH": "SELL"}[state.h1_trend]
            assert d.net_rr is not None and d.net_rr >= 1.5 - 1e-9
            assert d.stop_loss is not None and d.entry_price is not None and d.atr is not None
            assert abs(d.entry_price - d.stop_loss) <= 3.0 * d.atr + 1e-9
            assert d.risk_pct == 0.25 and d.risk_amount is not None
            assert d.risk_amount <= 10_000 * 0.25 / 100 + 1e-9
            assert not (cfg.c3b and obs.shock)
            if cfg.c2:
                ratio = cost_r(d, state.spread)
                assert ratio is not None and ratio <= COST_R_CAP + 1e-12
    assert seen > 100


def test_determinism() -> None:
    state = buy_state(**WIDE_BUT_CHEAP)
    assert run("CORE", state) == run("CORE", state)


def test_the_candidate_module_has_no_broker_or_io_path() -> None:
    tree = ast.parse(
        (ROOT / "src" / "xau_edge_v2" / "core" / "candidate.py").read_text(encoding="utf-8")
    )
    imported = {n.module or "" for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)} | {
        a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names
    }
    assert all(m.startswith(("xau_edge_v2.core", "dataclasses", "__future__")) for m in imported)


def test_the_control_is_not_edited_by_the_candidate() -> None:
    d = decide(buy_state(), CTX)
    replace(d)  # frozen dataclass copy works; the control's output type is untouched
    assert d.strategy_version == "1.1.0"
