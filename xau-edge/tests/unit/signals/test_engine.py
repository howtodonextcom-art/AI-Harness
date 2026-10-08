"""Signal engine from market frames: closed bars only, reproducible, WAIT without evidence."""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path

import numpy as np
import polars as pl
import pytest

from tests.conftest import make_bars
from xau_edge.domain.timeframe import Timeframe
from xau_edge.experiments.registry import ExperimentRegistry
from xau_edge.signals.engine import MarketFrames, generate_signal
from xau_edge.signals.schema import Direction, EvidenceStatus, NoTradeReason


def _walk(n: int, tf: Timeframe, seed: int) -> pl.DataFrame:
    rng = np.random.default_rng(seed)
    step = (tf.minutes / 5) ** 0.5
    close = (
        2000 + np.cumsum(rng.normal(0, step, n)) + 6 * np.sin(np.arange(n) * 5 / tf.minutes / 30)
    )
    open_ = np.concatenate([[2000.0], close[:-1]])
    high = np.maximum(open_, close) + np.abs(rng.normal(0, 0.4, n))
    low = np.minimum(open_, close) - np.abs(rng.normal(0, 0.4, n))
    return make_bars(n, tf).with_columns(
        pl.Series("open", open_),
        pl.Series("high", high),
        pl.Series("low", low),
        pl.Series("close", close),
        pl.Series("tick_volume", rng.integers(50, 500, n)),
    )


@pytest.fixture(scope="module")
def frames() -> MarketFrames:
    return MarketFrames(
        m5=_walk(12_000, Timeframe.M5, 1),
        m15=_walk(4_000, Timeframe.M15, 2),
        h1=_walk(1_000, Timeframe.H1, 3),
        h4=_walk(260, Timeframe.H4, 4),
    )


def test_without_validated_evidence_every_signal_is_wait(
    frames: MarketFrames, tmp_path: Path
) -> None:
    registry = ExperimentRegistry(tmp_path)
    at = frames.m15["timestamp"][3000] + timedelta(minutes=15)
    s = generate_signal(frames, at, registry)
    assert s.direction is Direction.WAIT
    assert NoTradeReason.NO_VALIDATED_EDGE in s.reasons
    assert s.evidence_status is EvidenceStatus.NONE
    assert s.timestamp == at
    assert s.historical_matches_count > 0
    assert s.prob_up is not None
    assert abs((s.prob_up or 0) + (s.prob_down or 0) + (s.prob_neutral or 0) - 1) < 1e-9
    assert "analogues" in s.probability_source
    assert s.higher_timeframe_bias


def test_no_calendar_means_news_risk_is_unknown_not_clear(
    frames: MarketFrames, tmp_path: Path
) -> None:
    at = frames.m15["timestamp"][3100] + timedelta(minutes=15)
    s = generate_signal(frames, at, ExperimentRegistry(tmp_path))
    assert NoTradeReason.NEWS_UNKNOWN in s.reasons


def test_the_signal_is_reproducible(frames: MarketFrames, tmp_path: Path) -> None:
    at = frames.m15["timestamp"][3200] + timedelta(minutes=15)
    a = generate_signal(frames, at, ExperimentRegistry(tmp_path))
    b = generate_signal(frames, at, ExperimentRegistry(tmp_path))
    assert a == b
    assert a.inputs_hash == b.inputs_hash


def test_bars_after_the_decision_time_cannot_change_the_signal(
    frames: MarketFrames, tmp_path: Path
) -> None:
    at = frames.m15["timestamp"][3000] + timedelta(minutes=15)
    full = generate_signal(frames, at, ExperimentRegistry(tmp_path))
    cut = MarketFrames(
        m5=frames.m5.filter(pl.col("timestamp") < at),
        m15=frames.m15.filter(pl.col("timestamp") < at),
        h1=frames.h1.filter(pl.col("timestamp") < at),
        h4=frames.h4.filter(pl.col("timestamp") < at),
    )
    shortened = generate_signal(cut, at, ExperimentRegistry(tmp_path))
    assert full == shortened


def test_too_early_for_any_history_is_wait_with_invalid_data(
    frames: MarketFrames, tmp_path: Path
) -> None:
    at = frames.m15["timestamp"][10] + timedelta(minutes=15)
    s = generate_signal(frames, at, ExperimentRegistry(tmp_path))
    assert s.direction is Direction.WAIT
    assert NoTradeReason.DATA_INVALID in s.reasons


def test_mid_bar_decision_times_use_only_the_last_closed_bar(
    frames: MarketFrames, tmp_path: Path
) -> None:
    registry = ExperimentRegistry(tmp_path)
    boundary = frames.m15["timestamp"][3000] + timedelta(minutes=15)
    aligned = generate_signal(frames, boundary, registry)
    for minutes in (1, 7, 14):
        mid = generate_signal(frames, boundary + timedelta(minutes=minutes), registry)
        assert mid.timestamp == boundary
        assert mid.inputs_hash == aligned.inputs_hash
        assert mid == aligned


def test_poisoned_future_bars_cannot_change_the_signal(
    frames: MarketFrames, tmp_path: Path
) -> None:
    at = frames.m15["timestamp"][3000] + timedelta(minutes=15)
    base = generate_signal(frames, at, ExperimentRegistry(tmp_path))

    def poison(frame: pl.DataFrame, minutes: int) -> pl.DataFrame:
        late = pl.col("timestamp") + timedelta(minutes=minutes) > at
        return frame.with_columns(
            *(
                pl.when(late).then(pl.col(c) * 9 + 50).otherwise(pl.col(c)).alias(c)
                for c in ("open", "high", "low", "close")
            ),
            pl.when(late).then(777).otherwise(pl.col("spread")).alias("spread"),
        )

    poisoned = MarketFrames(
        m5=poison(frames.m5, 5),
        m15=poison(frames.m15, 15),
        h1=poison(frames.h1, 60),
        h4=poison(frames.h4, 240),
    )
    assert generate_signal(poisoned, at, ExperimentRegistry(tmp_path)) == base
