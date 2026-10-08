"""Per-timeframe context frames and look-ahead-safe alignment across timeframes."""

from __future__ import annotations

import polars as pl

from xau_edge.domain.timeframe import Timeframe
from xau_edge.features.feature_set import FeatureConfig, build_features
from xau_edge.structure.frame import structure_frame


def build_context(bars: pl.DataFrame, timeframe: Timeframe) -> pl.DataFrame:
    """Features and market structure side by side, plus ``close``, for one timeframe.

    Both parts are keyed by ``timestamp`` (bar open) and ``available_at`` (bar close).
    """
    features = build_features(bars, timeframe, FeatureConfig())
    structure = structure_frame(bars, timeframe).drop("timestamp", "available_at")
    return features.hstack(structure).with_columns(bars["close"].alias("close"))


def align_to(
    base: pl.DataFrame, other: pl.DataFrame, columns: list[str], *, prefix: str
) -> pl.DataFrame:
    """Attach ``columns`` of ``other`` (a slower timeframe) to every row of ``base``.

    Each base row receives the LATEST ``other`` row that had already closed at the base row's
    decision time (``other.available_at <= base.available_at``); rows before the first closed bar
    get nulls. This is the only sanctioned way to combine timeframes: joining on ``timestamp``
    would hand a base bar the not-yet-finished higher-timeframe bar.
    """
    missing = [c for c in ["available_at", *columns] if c not in other.columns]
    if missing or "available_at" not in base.columns:
        msg = f"missing column(s): {', '.join(missing) or 'available_at in base'}"
        raise ValueError(msg)
    if not base["available_at"].is_sorted():
        msg = "base must be sorted by available_at"
        raise ValueError(msg)
    right = other.sort("available_at").select(
        pl.col("available_at").alias("_key"), *[pl.col(c).alias(f"{prefix}{c}") for c in columns]
    )
    return base.join_asof(right, left_on="available_at", right_on="_key", strategy="backward").drop(
        "_key"
    )
