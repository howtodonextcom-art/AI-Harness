"""Rule-based regime classification: priorities, causality, warm-up, configuration."""

from __future__ import annotations

import numpy as np
import pytest

from xau_edge.structure.regime import Regime, RegimeConfig, classify_regime

N = 700
CFG = RegimeConfig()


def _base(adx: float = 30.0, plus: float = 30.0, minus: float = 10.0, atr: float = 1.0):  # type: ignore[no-untyped-def]
    """Flat inputs; each test then overrides the bar it cares about (index 650)."""
    return {
        "adx": np.full(N, adx),
        "plus_di": np.full(N, plus),
        "minus_di": np.full(N, minus),
        "atr": np.full(N, atr),
        "high": np.full(N, 101.0),
        "low": np.full(N, 100.0),  # range 1 = ATR: unremarkable
    }


def _label(inp: dict[str, np.ndarray], at: int = 650) -> str | None:
    label: str | None = classify_regime(**inp, config=CFG)[at]
    return label


def test_trend_up_and_down_follow_directional_indicators() -> None:
    assert _label(_base()) == Regime.TREND_UP.value
    assert _label(_base(plus=10.0, minus=30.0)) == Regime.TREND_DOWN.value


def test_low_adx_is_range() -> None:
    assert _label(_base(adx=15.0)) == Regime.RANGE.value
    assert _label(_base(adx=24.99)) == Regime.RANGE.value
    assert _label(_base(adx=25.0)) == Regime.TREND_UP.value


def test_high_volatility_when_atr_is_well_above_its_history() -> None:
    inp = _base(adx=15.0)
    inp["atr"][650] = 1.5  # ratio exactly at the threshold
    assert _label(inp) == Regime.HIGH_VOLATILITY.value
    inp["atr"][650] = 1.49
    assert _label(inp) == Regime.RANGE.value


def test_low_volatility_when_atr_is_well_below_its_history_and_no_trend() -> None:
    inp = _base(adx=15.0)
    inp["atr"][650] = 0.67
    assert _label(inp) == Regime.LOW_VOLATILITY.value
    inp["atr"][650] = 0.68
    assert _label(inp) == Regime.RANGE.value


def test_shock_is_a_bar_much_larger_than_the_previous_bars_atr() -> None:
    inp = _base()
    inp["high"][650] = 104.0  # range 4 >= 3 x previous ATR
    assert _label(inp) == Regime.SHOCK.value
    inp["high"][650] = 102.9
    assert _label(inp) != Regime.SHOCK.value
    inp["high"][650] = 103.0  # exactly 3 x the previous ATR counts as a shock
    assert _label(inp) == Regime.SHOCK.value


def test_shock_ignores_the_shock_bars_own_atr_increase() -> None:
    inp = _base()
    inp["high"][650] = 104.0
    inp["atr"][650] = 1.5  # ATR already absorbed part of the shock; previous ATR is still 1.0
    assert _label(inp) == Regime.SHOCK.value


def test_priority_shock_over_high_vol_over_trend_over_low_vol() -> None:
    inp = _base()
    inp["atr"][650] = 2.0
    assert _label(inp) == Regime.HIGH_VOLATILITY.value  # beats the trend
    inp["high"][650] = 106.0
    assert _label(inp) == Regime.SHOCK.value  # beats high volatility
    low = _base(adx=30.0)
    low["atr"][650] = 0.5
    assert _label(low) == Regime.TREND_UP.value  # a trend beats low volatility


def test_warmup_and_missing_inputs_are_unknown() -> None:
    inp = _base()
    labels = classify_regime(**inp, config=CFG)
    assert all(label is None for label in labels[: CFG.min_history])
    assert labels[CFG.min_history + 5] is not None
    nan_adx = _base()
    nan_adx["adx"][650] = np.nan
    assert _label(nan_adx) is None


def test_history_excludes_the_current_bar() -> None:
    cfg = RegimeConfig(vol_window=10, min_history=5)
    atr = np.array([1.0] * 5 + [3.0] * 5 + [4.0, 1.0, 1.0])  # past median at bar 10 is 2.0
    n = atr.size
    labels = classify_regime(
        adx=np.full(n, 15.0),
        plus_di=np.full(n, 30.0),
        minus_di=np.full(n, 10.0),
        atr=atr,
        high=np.full(n, 101.0),
        low=np.full(n, 100.0),
        config=cfg,
    )
    # excluding the current bar: 4.0 / 2.0 = 2 -> HIGH_VOLATILITY; including it the median
    # would be 3.0 and the ratio 1.33 -> RANGE
    assert labels[10] == Regime.HIGH_VOLATILITY.value


def test_equal_directional_indicators_are_not_a_trend() -> None:
    assert _label(_base(plus=20.0, minus=20.0)) == Regime.RANGE.value


def test_a_zero_previous_atr_cannot_trigger_a_shock() -> None:
    inp = _base(adx=15.0)
    inp["atr"][649] = 0.0
    inp["high"][650] = inp["low"][650]
    assert _label(inp) is None


def test_labels_never_repaint() -> None:
    rng = np.random.default_rng(2)
    atr = 1 + 0.3 * np.abs(rng.normal(size=N))
    inp = {
        "adx": rng.uniform(5, 50, N),
        "plus_di": rng.uniform(5, 40, N),
        "minus_di": rng.uniform(5, 40, N),
        "atr": atr,
        "high": 100 + rng.uniform(0.2, 3.5, N),
        "low": np.full(N, 100.0),
    }
    full = classify_regime(**inp, config=CFG)
    cut = 450
    part = classify_regime(**{k: v[:cut] for k, v in inp.items()}, config=CFG)
    assert list(full[:cut]) == list(part)


def test_only_documented_labels_are_produced() -> None:
    rng = np.random.default_rng(4)
    inp = {
        "adx": rng.uniform(5, 50, N),
        "plus_di": rng.uniform(5, 40, N),
        "minus_di": rng.uniform(5, 40, N),
        "atr": 1 + rng.uniform(0, 2, N),
        "high": 100 + rng.uniform(0.2, 6, N),
        "low": np.full(N, 100.0),
    }
    seen = {x for x in classify_regime(**inp, config=CFG) if x is not None}
    assert seen <= {r.value for r in Regime}
    assert len(seen) >= 4


def test_config_validation() -> None:
    with pytest.raises(ValueError, match="low_vol_ratio"):
        RegimeConfig(low_vol_ratio=1.2)
    with pytest.raises(ValueError, match="high_vol_ratio"):
        RegimeConfig(high_vol_ratio=0.9)
    with pytest.raises(ValueError, match="min_history"):
        RegimeConfig(vol_window=50, min_history=60)


def test_inputs_must_have_equal_length() -> None:
    inp = _base()
    inp["atr"] = inp["atr"][:-1]
    with pytest.raises(ValueError, match="length"):
        classify_regime(**inp, config=CFG)
