"""Day-block bootstrap for dependent observations."""

from __future__ import annotations

import numpy as np
import pytest

from xau_edge.evaluation.bootstrap import block_bootstrap_ci


def test_interval_brackets_a_clear_positive_mean() -> None:
    rng = np.random.default_rng(1)
    values = rng.normal(0.5, 1.0, 600)
    blocks = np.repeat(np.arange(60), 10)
    lo, hi = block_bootstrap_ci(values, blocks, seed=3)
    assert lo < values.mean() < hi
    assert lo > 0


def test_interval_includes_zero_for_noise() -> None:
    rng = np.random.default_rng(2)
    values = rng.normal(0.0, 1.0, 600)
    blocks = np.repeat(np.arange(60), 10)
    lo, hi = block_bootstrap_ci(values, blocks, seed=3)
    assert lo < 0 < hi


def test_same_seed_gives_the_same_interval_and_other_seed_differs() -> None:
    values = np.random.default_rng(3).normal(size=300)
    blocks = np.repeat(np.arange(30), 10)
    a = block_bootstrap_ci(values, blocks, seed=7)
    assert a == block_bootstrap_ci(values, blocks, seed=7)
    assert a != block_bootstrap_ci(values, blocks, seed=8)


def test_blocks_are_resampled_whole_so_correlated_data_widens_the_interval() -> None:
    rng = np.random.default_rng(4)
    day_effect = np.repeat(rng.normal(0, 1, 30), 20)  # strong within-day correlation
    values = day_effect + rng.normal(0, 0.1, 600)
    blocks = np.repeat(np.arange(30), 20)
    block_lo, block_hi = block_bootstrap_ci(values, blocks, seed=1)
    iid_lo, iid_hi = block_bootstrap_ci(values, np.arange(600), seed=1)
    assert (block_hi - block_lo) > 2 * (iid_hi - iid_lo)


def test_wider_confidence_level_gives_a_wider_interval() -> None:
    values = np.random.default_rng(5).normal(size=400)
    blocks = np.repeat(np.arange(40), 10)
    narrow = block_bootstrap_ci(values, blocks, alpha=0.2, seed=1)
    wide = block_bootstrap_ci(values, blocks, alpha=0.01, seed=1)
    assert (wide[1] - wide[0]) > (narrow[1] - narrow[0])


def test_weighted_statistic_is_supported() -> None:
    values = np.array([1.0] * 50 + [3.0] * 50)
    blocks = np.repeat(np.arange(10), 10)
    lo, hi = block_bootstrap_ci(values, blocks, seed=1, statistic=np.median)
    assert 1.0 <= lo <= hi <= 3.0


def test_input_validation() -> None:
    with pytest.raises(ValueError, match="length"):
        block_bootstrap_ci(np.ones(5), np.arange(4))
    with pytest.raises(ValueError, match="empty"):
        block_bootstrap_ci(np.array([]), np.array([]))
    with pytest.raises(ValueError, match="alpha"):
        block_bootstrap_ci(np.ones(5), np.arange(5), alpha=1.5)
    with pytest.raises(ValueError, match="finite"):
        block_bootstrap_ci(np.array([1.0, np.nan]), np.arange(2))
