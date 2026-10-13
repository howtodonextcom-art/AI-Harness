"""Market structure: swings, HH/HL/LH/LL, trend, BOS, CHoCH, support/resistance.

The hand-built series below has pivots that were worked out on paper (left = right = 2):
swing highs 12, 13, 14, 15 at bars 2, 6, 10, 14 (confirmed 2 bars later), swing lows 9, 10, 11 at
bars 4, 8, 12 (confirmed at 6, 10, 14).
"""

from __future__ import annotations

import numpy as np
import pytest

from xau_edge.structure.swings import StructureConfig, analyse_structure

H = np.array(
    [10, 11, 12, 11, 10, 11, 13, 12, 11, 12, 14, 13, 12, 13, 15, 14, 13, 12, 11, 10, 9, 8, 9, 10],
    dtype=float,
)
L = H - 1.0
C = H - 0.25
CFG = StructureConfig(left=2, right=2)


def _run(h: np.ndarray = H, low: np.ndarray = L, c: np.ndarray = C):  # type: ignore[no-untyped-def]
    return analyse_structure(h, low, c, CFG)


def test_swings_are_reported_only_at_confirmation() -> None:
    s = _run()
    assert np.flatnonzero(s.new_swing_high).tolist() == [4, 8, 12, 16]
    assert np.flatnonzero(s.new_swing_low)[:3].tolist() == [6, 10, 14]
    assert np.isnan(s.last_swing_high[:4]).all()
    assert s.last_swing_high[4] == 12
    assert s.last_swing_high[8] == 13
    assert s.last_swing_low[6] == 9
    assert s.last_swing_low[10] == 10


def test_labels_and_trend() -> None:
    s = _run()
    assert s.high_label[8] == 1  # 13 > 12: higher high
    assert s.low_label[10] == 1  # 10 > 9: higher low
    assert s.trend[8] == 0  # no second swing low yet
    assert s.trend[10] == 1
    assert s.trend[14] == 1


def test_break_of_structure_in_trend_and_breakout_from_unknown() -> None:
    s = _run()
    assert s.bos[6] == 1  # first break, trend unknown: breakout
    assert s.bos[10] == 1
    assert s.bos[14] == 1  # continuation inside a confirmed uptrend
    assert s.choch[14] == 0


def test_change_of_character_when_uptrend_breaks_its_last_swing_low() -> None:
    s = _run()
    assert s.trend[17] == 1
    assert s.choch[18] == -1
    assert s.bos[18] == 0


def test_each_swing_level_breaks_only_once() -> None:
    s = _run()
    assert np.count_nonzero(s.bos[:15]) == 3
    assert (s.bos[7:10] == 0).all()


def test_support_and_resistance_are_nearest_unbroken_levels() -> None:
    s = _run()
    j = 14
    assert s.support[j] == 11  # swing low 11 confirmed at 14; below close 14.75
    assert np.isnan(s.resistance[j])  # every confirmed swing high has been broken
    j = 17
    assert s.resistance[j] == 15
    assert s.support[j] == 11


def test_structure_never_repaints() -> None:
    full = _run()
    for cut in range(8, H.size):
        part = analyse_structure(H[:cut], L[:cut], C[:cut], CFG)
        for name in full._fields:
            np.testing.assert_array_equal(
                getattr(full, name)[:cut], getattr(part, name), err_msg=f"{name} cut={cut}"
            )


def test_random_walk_never_repaints_and_labels_are_valid() -> None:
    rng = np.random.default_rng(5)
    close = 100 + np.cumsum(rng.normal(0, 1, 600))
    high = close + np.abs(rng.normal(0, 0.5, 600))
    low = close - np.abs(rng.normal(0, 0.5, 600))
    cfg = StructureConfig(left=3, right=3)
    full = analyse_structure(high, low, close, cfg)
    part = analyse_structure(high[:400], low[:400], close[:400], cfg)
    for name in full._fields:
        np.testing.assert_array_equal(getattr(full, name)[:400], getattr(part, name))
    assert set(np.unique(full.trend)) <= {-1, 0, 1}
    assert set(np.unique(full.bos)) <= {-1, 0, 1}
    assert not (full.bos != 0)[full.choch != 0].any()  # a bar is BOS or CHoCH, never both


def test_support_below_and_resistance_above_close_when_present() -> None:
    rng = np.random.default_rng(8)
    close = 100 + np.cumsum(rng.normal(0, 1, 500))
    high, low = close + 0.4, close - 0.4
    s = analyse_structure(high, low, close, StructureConfig())
    sup = ~np.isnan(s.support)
    res = ~np.isnan(s.resistance)
    assert (s.support[sup] < close[sup]).all()
    assert (s.resistance[res] > close[res]).all()


def test_short_input_has_no_structure() -> None:
    s = analyse_structure(H[:4], L[:4], C[:4], CFG)
    assert np.isnan(s.last_swing_high).all()
    assert (s.trend == 0).all()
    assert analyse_structure(H[:0], L[:0], C[:0], CFG).trend.size == 0


def test_config_and_input_validation() -> None:
    with pytest.raises(ValueError, match="left"):
        StructureConfig(left=0)
    with pytest.raises(ValueError, match="high"):
        analyse_structure(L, H, C, CFG)  # high below low


# ---- ties, exact-level closes, nearest levels, labels, mirror symmetry ----------------------

ONE = StructureConfig(left=1, right=1)


def _flat_low(h: list[float]) -> tuple[np.ndarray, np.ndarray]:
    high = np.array(h, dtype=float)
    return high, high - 1.0


def test_plateau_of_equal_highs_gives_a_single_swing_high() -> None:
    high, low = _flat_low([1, 3, 3, 1, 0.5])
    s = analyse_structure(high, low, high - 0.5, ONE)
    assert s.new_swing_high.sum() == 1
    assert s.last_swing_high[-1] == 3


def test_plateau_of_equal_lows_gives_a_single_swing_low() -> None:
    low = np.array([5, 2, 2, 5, 6], dtype=float)
    high = low + 1.0
    s = analyse_structure(high, low, low + 0.5, ONE)
    assert s.new_swing_low.sum() == 1
    assert s.last_swing_low[-1] == 2


def test_a_close_exactly_on_the_swing_level_is_not_a_break() -> None:
    high = np.array([1, 3, 1, 2, 3.0, 3.5])
    low = high - 1.0
    close = np.array([0.5, 2.5, 0.5, 1.5, 3.0, 3.01])
    s = analyse_structure(high, low, close, ONE)
    assert s.bos[4] == 0  # close == 3.0 == swing high
    assert s.bos[5] == 1


def test_lower_highs_and_lower_lows_are_labelled_minus_one() -> None:
    h = [2, 9, 2, 3, 7, 1.5, 2, 5, 1, 1.2]
    high, low = np.array(h, dtype=float), np.array(h, dtype=float) - 0.5
    s = analyse_structure(high, low, high - 0.25, ONE)
    assert s.high_label[-1] == -1
    assert s.low_label[-1] == -1
    assert s.trend[-1] == -1


def test_resistance_is_the_nearest_unbroken_swing_high_above_the_close() -> None:
    h = [1, 20, 1, 2, 18, 2, 1, 15, 1, 3, 4, 5]
    high = np.array(h, dtype=float)
    low = high - 0.5
    close = high - 0.25
    s = analyse_structure(high, low, close, ONE)
    j = len(h) - 1
    assert s.resistance[j] == 15  # 20, 18 and 15 are all unbroken: the lowest one above close wins


def _mirror(x: np.ndarray) -> np.ndarray:
    return 100.0 - x


def test_mirrored_prices_give_mirrored_structure_on_the_hand_series() -> None:
    a = analyse_structure(H, L, C, CFG)
    b = analyse_structure(_mirror(L), _mirror(H), _mirror(C), CFG)
    _assert_mirrored(a, b)


def test_mirrored_prices_give_mirrored_structure_on_random_walks() -> None:
    for seed in range(5):
        rng = np.random.default_rng(100 + seed)
        close = 100 + np.cumsum(rng.normal(0, 1, 500))
        high = close + np.abs(rng.normal(0, 0.5, 500))
        low = close - np.abs(rng.normal(0, 0.5, 500))
        a = analyse_structure(high, low, close, StructureConfig())
        b = analyse_structure(_mirror(low), _mirror(high), _mirror(close), StructureConfig())
        _assert_mirrored(a, b)


def _assert_mirrored(a, b) -> None:  # type: ignore[no-untyped-def]
    np.testing.assert_array_equal(a.trend, -b.trend)
    np.testing.assert_array_equal(a.bos, -b.bos)
    np.testing.assert_array_equal(a.choch, -b.choch)
    np.testing.assert_array_equal(a.high_label, -b.low_label)
    np.testing.assert_array_equal(a.low_label, -b.high_label)
    np.testing.assert_array_equal(a.new_swing_high, b.new_swing_low)
    np.testing.assert_allclose(a.support, _mirror(b.resistance), equal_nan=True)
    np.testing.assert_allclose(a.resistance, _mirror(b.support), equal_nan=True)


def test_trend_is_only_updated_when_a_swing_is_confirmed_not_on_a_break() -> None:
    s = _run()
    assert s.choch[18] == -1
    assert (s.trend[16:22] == 1).all()  # carried across the CHoCH until new swings confirm


def test_event_type_uses_the_trend_of_the_previous_bar() -> None:
    for seed in range(4):
        rng = np.random.default_rng(300 + seed)
        close = 100 + np.cumsum(rng.normal(0, 1, 800))
        high = close + np.abs(rng.normal(0, 0.5, 800))
        low = close - np.abs(rng.normal(0, 0.5, 800))
        s = analyse_structure(high, low, close, StructureConfig())
        direction = s.bos.astype(int) + s.choch.astype(int)
        for j in np.flatnonzero(direction)[1:]:
            d, prior = direction[j], int(s.trend[j - 1])
            assert (s.choch[j] != 0) == (prior == -d), (seed, j)
            assert (s.bos[j] != 0) == (prior != -d), (seed, j)


def test_an_outside_bar_can_be_swing_high_and_swing_low_at_once() -> None:
    high = np.array([5, 5, 10, 5, 5.0])
    low = np.array([4, 4, 0, 4, 4.0])
    s = analyse_structure(high, low, np.full(5, 4.5), ONE)
    assert s.new_swing_high[3] == 1
    assert s.new_swing_low[3] == 1
    assert s.last_swing_high[3] == 10
    assert s.last_swing_low[3] == 0
