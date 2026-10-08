"""Model probabilities -> trade signals, probability scoring report, model artifacts."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np
import polars as pl
import pytest
from sklearn.linear_model import LogisticRegression

from xau_edge.models.artifact import ModelArtifact, load_artifact_metadata, save_artifact
from xau_edge.models.scoring import ProbabilityReport, score_predictions
from xau_edge.models.signals import ModelSignalConfig, model_signals
from xau_edge.strategies.baselines import SIGNAL_COLUMNS

T0 = datetime(2026, 2, 2, tzinfo=UTC)


def _pred(
    p_down: list[float], p_neutral: list[float], p_up: list[float], y: list[int] | None = None
) -> pl.DataFrame:
    n = len(p_up)
    ts = [T0 + timedelta(minutes=15 * i) for i in range(n)]
    return pl.DataFrame(
        {
            "timestamp": pl.Series(ts, dtype=pl.Datetime("us", "UTC")),
            "decision_time": pl.Series(
                [t + timedelta(minutes=15) for t in ts], dtype=pl.Datetime("us", "UTC")
            ),
            "index": list(range(n)),
            "fold": [0] * n,
            "y": y if y is not None else [1] * n,
            "p_down": p_down,
            "p_neutral": p_neutral,
            "p_up": p_up,
            "atr": [2.0] * n,
            "regime": ["RANGE"] * n,
        }
    )


def test_long_short_and_wait_follow_the_edge_and_minimum_probability() -> None:
    pred = _pred(
        p_down=[0.1, 0.5, 0.3, 0.45, 0.2],
        p_neutral=[0.3, 0.2, 0.4, 0.15, 0.5],
        p_up=[0.6, 0.3, 0.3, 0.40, 0.3],
    )
    cfg = ModelSignalConfig(edge_threshold=0.15, min_probability=0.40, outcome_horizon=20)
    sig = model_signals(pred, cfg)
    assert sig.columns[: len(SIGNAL_COLUMNS)] == list(SIGNAL_COLUMNS)
    # row0 edge +0.5 long ; row1 edge -0.2 short (p_down 0.5 >= 0.40) ; row2 wait ;
    # row3 edge -0.05 wait ; row4 edge +0.1 wait
    assert sig["direction"].to_list() == [1, -1]


def test_thresholds_are_inclusive() -> None:
    pred = _pred([0.25], [0.35], [0.40])  # edge 0.15 (float), p_up exactly the minimum
    cfg = ModelSignalConfig(edge_threshold=0.15, min_probability=0.40, outcome_horizon=20)
    assert model_signals(pred, cfg)["direction"].to_list() == [1]


def test_signals_carry_atr_regime_exit_distances_and_hold() -> None:
    sig = model_signals(
        _pred([0.1], [0.2], [0.7]),
        ModelSignalConfig(stop_atr=1.2, target_atr=2.4, outcome_horizon=12),
    )
    row = sig.row(0, named=True)
    assert row["atr"] == 2.0
    assert row["stop_atr"] == 1.2
    assert row["target_atr"] == 2.4
    assert row["max_hold_bars"] == 12
    assert row["regime"] == "RANGE"
    assert row["decision_time"] == T0 + timedelta(minutes=15)


def test_signals_never_use_the_label_column() -> None:
    a = model_signals(_pred([0.1] * 3, [0.2] * 3, [0.7] * 3, y=[0, 1, 2]))
    b = model_signals(_pred([0.1] * 3, [0.2] * 3, [0.7] * 3, y=[2, 2, 2]))
    assert a.equals(b)


def test_empty_predictions_give_no_signals() -> None:
    assert model_signals(pl.DataFrame()).height == 0


def test_scoring_report_compares_with_the_base_rate() -> None:
    n = 300
    rng = np.random.default_rng(0)
    y = rng.integers(0, 3, n)
    good = np.eye(3)[y] * 0.5 + 1 / 6  # informative probabilities
    pred = _pred(good[:, 0].tolist(), good[:, 1].tolist(), good[:, 2].tolist(), y.tolist())
    report = score_predictions(pred, base_rates=np.array([1 / 3, 1 / 3, 1 / 3]))
    assert isinstance(report, ProbabilityReport)
    assert report.n == n
    assert report.log_loss < report.base_log_loss
    assert report.brier < report.base_brier
    assert report.beats_base_rate
    assert len(report.ece_per_class) == 3
    json.dumps(report.as_dict(), allow_nan=False)


def test_scoring_report_flags_a_model_that_does_not_beat_the_base_rate() -> None:
    n = 300
    rng = np.random.default_rng(1)
    y = rng.integers(0, 3, n)
    noise = rng.dirichlet([1, 1, 1], n)  # unrelated to y
    pred = _pred(noise[:, 0].tolist(), noise[:, 1].tolist(), noise[:, 2].tolist(), y.tolist())
    report = score_predictions(pred, base_rates=np.array([1 / 3, 1 / 3, 1 / 3]))
    assert not report.beats_base_rate


def test_scoring_empty_predictions_is_an_error() -> None:
    with pytest.raises(ValueError, match="no predictions"):
        score_predictions(pl.DataFrame(), base_rates=np.array([1 / 3] * 3))


def test_artifact_roundtrip_records_the_required_metadata(tmp_path: Path) -> None:
    model = LogisticRegression().fit(np.array([[0.0], [1.0], [2.0], [3.0]]), np.array([0, 0, 1, 1]))
    art = ModelArtifact(
        name="logistic",
        version="1",
        training_period=("2025-05-01", "2025-12-31"),
        feature_version="1",
        hyperparameters={"C": 0.1},
        metrics={"log_loss": 1.0},
        trained_at="2026-10-08T00:00:00+00:00",
        git_commit="deadbeef",
    )
    folder = save_artifact(tmp_path, art, model)
    meta = load_artifact_metadata(folder)
    for key in (
        "name",
        "version",
        "training_period",
        "feature_version",
        "hyperparameters",
        "metrics",
        "trained_at",
        "git_commit",
        "model_sha256",
    ):
        assert key in meta
    assert meta["model_sha256"]


def test_artifact_metadata_load_detects_a_swapped_model_file(tmp_path: Path) -> None:
    model = LogisticRegression().fit(np.array([[0.0], [1.0], [2.0], [3.0]]), np.array([0, 0, 1, 1]))
    art = ModelArtifact(
        name="m",
        version="1",
        training_period=("a", "b"),
        feature_version="1",
        hyperparameters={},
        metrics={},
        trained_at="t",
        git_commit="c",
    )
    folder = save_artifact(tmp_path, art, model)
    (folder / "model.joblib").write_bytes(b"tampered")
    with pytest.raises(ValueError, match="hash"):
        load_artifact_metadata(folder, verify_model=True)
