"""ML M0/M1 infrastructure: causal features, label contract, purge, leakage guards (no model)."""

from __future__ import annotations

import numpy as np
import pytest

from tests.unit.test_core import frame
from xau_edge_v2.core.frames import Frame
from xau_edge_v2.domain.contract import Timeframe
from xau_edge_v2.ml import m0_contract as m0


def perturbed_future(f: Frame, t: int, seed: int = 0) -> Frame:
    """The same frame with every bar AFTER ``t`` replaced by different (valid) values."""
    rng = np.random.default_rng(seed)
    o, h, lo, c = f.open.copy(), f.high.copy(), f.low.copy(), f.close.copy()
    n = f.height - t - 1
    close = c[t] + np.cumsum(rng.normal(0, 3.0, n))
    open_ = np.concatenate([[c[t]], close[:-1]])
    o[t + 1 :], c[t + 1 :] = open_, close
    h[t + 1 :] = np.maximum(open_, close) + rng.random(n) * 2
    lo[t + 1 :] = np.minimum(open_, close) - rng.random(n) * 2
    spread = f.spread.copy()
    spread[t + 1 :] *= 3  # only the future changes
    return Frame(f.timeframe, f.open_us, o, h, lo, c, f.tick_volume, spread)


def test_every_feature_has_provenance_and_is_causal() -> None:
    assert [f.name for f in m0.FEATURES] == list(m0.FEATURE_NAMES)
    assert all(f.causal and f.source and f.lookback >= 1 for f in m0.FEATURES)
    x, valid = m0.build_features(frame(Timeframe.M15, 1500, seed=3))
    assert x.shape[1] == len(m0.FEATURE_NAMES) and valid.sum() > 1000


@pytest.mark.parametrize("t", [400, 900, 1300])
def test_features_at_t_do_not_depend_on_any_later_bar(t: int) -> None:
    f = frame(Timeframe.M15, 1600, seed=5)
    x, valid = m0.build_features(f)
    x2, valid2 = m0.build_features(perturbed_future(f, t))
    np.testing.assert_allclose(x[: t + 1], x2[: t + 1], equal_nan=True)
    assert (valid[: t + 1] == valid2[: t + 1]).all()


def test_the_harness_detects_a_leaky_feature() -> None:
    """Meta-test: the invariance check must FAIL for a feature that peeks one bar ahead."""
    f = frame(Timeframe.M15, 800, seed=2)

    def leaky(fr: Frame) -> np.ndarray:  # type: ignore[type-arg]
        out = np.full(fr.height, np.nan)
        out[:-1] = fr.close[1:] - fr.close[:-1]  # uses bar t+1
        return out

    a, b = leaky(f), leaky(perturbed_future(f, 400))
    assert not np.allclose(a[:401], b[:401], equal_nan=True)


def test_volatility_label_is_future_only_and_known_at_t_plus_h() -> None:
    f = frame(Timeframe.M15, 1200, seed=7)
    y, known = m0.label_vol_expansion(f)
    t = np.arange(f.height)
    assert (known - t == m0.HORIZON_VOL).all()
    y2, _ = m0.label_vol_expansion(perturbed_future(f, 600))
    ok = np.isfinite(y) & np.isfinite(y2)
    # a label at t <= 600 - 12 reads only bars <= 600: unchanged; later ones may change
    safe = ok & (t <= 600 - m0.HORIZON_VOL)
    assert (y[safe] == y2[safe]).all()
    assert np.isfinite(y).sum() > 900 and set(np.unique(y[np.isfinite(y)])) <= {0.0, 1.0}


def test_the_label_is_not_derivable_from_the_features_at_t() -> None:
    """No feature may contain the label: its correlation with the label stays modest."""
    f = frame(Timeframe.M15, 6000, seed=11)
    x, valid = m0.build_features(f)
    y, _ = m0.label_vol_expansion(f)
    ok = valid & np.isfinite(y)
    corr = [abs(np.corrcoef(x[ok, j], y[ok])[0, 1]) for j in range(x.shape[1])]
    assert max(c for c in corr if np.isfinite(c)) < 0.6


def test_break_failed_labels_are_known_only_after_the_window() -> None:
    f = frame(Timeframe.M15, 4000, seed=13)
    idx, y, known = m0.label_break_failed(f)
    assert idx.size > 50 and set(np.unique(y)) <= {0.0, 1.0}
    assert (known - idx == m0.FAIL_HORIZON).all() and known.max() < f.height
    cut = 2000
    i2, y2, _ = m0.label_break_failed(f.head(cut))
    keep = idx < cut - m0.FAIL_HORIZON
    np.testing.assert_array_equal(i2, idx[keep])
    np.testing.assert_array_equal(y2, y[keep])  # appending bars never changes an old label


def test_the_purge_removes_every_row_whose_label_touches_the_test_block() -> None:
    n, h = 1000, m0.HORIZON_VOL
    known = np.arange(n) + h
    train = m0.purged_train_index(n, known, 500, 600, embargo=5)
    assert train.max() < 500
    assert (known[train] < 500 - 5).all()  # label window ended before the embargo
    kfold = m0.purged_train_index(n, known, 500, 600, embargo=5, walk_forward=False)
    after = kfold[kfold >= 500]
    assert after.min() >= 605  # rows after the block start beyond the embargo
    assert not np.isin(np.arange(488, 605), kfold).any()  # nothing from the leaky/embargo band


def test_the_manifest_is_deterministic_and_states_no_authority() -> None:
    f = frame(Timeframe.M15, 1500, seed=3)
    x, valid = m0.build_features(f)
    y, _ = m0.label_vol_expansion(f)
    a = m0.dataset_manifest(f, x, y, valid, "vol_expansion_12.v1")
    b = m0.dataset_manifest(f, x, y, valid, "vol_expansion_12.v1")
    assert a == b and a["authority"] == "NONE" and a["pnl_in_labels"] is False
