"""Read-only data access for the API: frames, features, regimes, analogues, registry views."""

from __future__ import annotations

import math
import threading
from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import polars as pl

from xau_edge.api.bot import BotContext
from xau_edge.domain.timeframe import Timeframe
from xau_edge.execution.trader import PaperTrader
from xau_edge.experiments.registry import ExperimentRegistry
from xau_edge.models.artifact import load_artifact_metadata
from xau_edge.patterns.representation import pattern_values, window_validity
from xau_edge.patterns.search import PatternIndex, SearchConfig
from xau_edge.risk.engine import RiskLimits
from xau_edge.risk.prop_rules import PropProfile
from xau_edge.signals.engine import MarketFrames
from xau_edge.signals.schema import Signal
from xau_edge.strategies.context import build_context

SYMBOL = "XAUUSD"
WINDOW = 30
OUTCOME_BARS = 20


def jsonable(value: Any) -> Any:
    """Make nested values JSON-safe: NaN/inf become null, datetimes become ISO strings."""
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(k): jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [jsonable(v) for v in value]
    if isinstance(value, np.generic):
        return jsonable(value.item())
    return value


def json_dict(value: Any) -> dict[str, Any]:
    """``jsonable`` for a mapping."""
    out = jsonable(value)
    if not isinstance(out, dict):
        msg = "expected a mapping"
        raise TypeError(msg)
    return out


def json_list(value: Any) -> list[dict[str, Any]]:
    """``jsonable`` for a list of mappings."""
    out = jsonable(value)
    if not isinstance(out, list):
        msg = "expected a list"
        raise TypeError(msg)
    return out


@dataclass
class ApiContext:
    """Everything the endpoints read. Nothing here can place an order."""

    load_frames: Callable[[], MarketFrames]
    registry: ExperimentRegistry
    prop: PropProfile
    limits: RiskLimits = field(default_factory=RiskLimits)
    models_dir: Path = Path("models")
    signal_provider: Callable[[datetime], Signal] | None = None
    paper: PaperTrader | None = None
    bot: BotContext | None = None
    clock: Callable[[], datetime] = field(default=lambda: datetime.now(UTC))
    max_data_age_minutes: int = 45
    _paper_lock: threading.Lock = field(default_factory=threading.Lock)
    journal_path: Path = Path("data/paper/journal.jsonl")
    max_cache: int = 16
    _frames: MarketFrames | None = None
    _cache: OrderedDict[tuple[str, datetime], Any] = field(default_factory=OrderedDict)
    _lock: threading.Lock = field(default_factory=threading.Lock)
    _heavy: threading.Semaphore = field(default_factory=lambda: threading.Semaphore(2))

    def cached(self, kind: str, key: datetime, compute: Callable[[], Any]) -> Any:
        """Memoise a per-bar result (bounded LRU); heavy work runs at most twice at once."""
        with self._lock:
            if (kind, key) in self._cache:
                self._cache.move_to_end((kind, key))
                return self._cache[(kind, key)]
        with self._heavy:
            value = compute()
        with self._lock:
            self._cache[(kind, key)] = value
            while len(self._cache) > self.max_cache:
                self._cache.popitem(last=False)
        return value

    def frames(self) -> MarketFrames:
        """Load (once) and return the validated frames."""
        if self._frames is None:
            self._frames = self.load_frames()
        return self._frames


def bars_view(frames: MarketFrames, timeframe: Timeframe, limit: int) -> list[dict[str, Any]]:
    """The last ``limit`` bars as plain records (open time, OHLC, tick volume, spread)."""
    frame = {
        Timeframe.M5: frames.m5,
        Timeframe.M15: frames.m15,
        Timeframe.H1: frames.h1,
        Timeframe.H4: frames.h4,
    }[timeframe]
    tail = frame.tail(limit).select(
        "timestamp", "open", "high", "low", "close", "tick_volume", "spread"
    )
    return json_list(tail.to_dicts())


def features_view(frames: MarketFrames, timeframe: Timeframe, limit: int) -> list[dict[str, Any]]:
    """The last ``limit`` rows of features and structure for one timeframe."""
    frame = {
        Timeframe.M5: frames.m5,
        Timeframe.M15: frames.m15,
        Timeframe.H1: frames.h1,
        Timeframe.H4: frames.h4,
    }[timeframe]
    ctx = build_context(frame.tail(limit + 600), timeframe)  # warm-up for the slow indicators
    return json_list(ctx.tail(limit).to_dicts())


def regime_view(frames: MarketFrames) -> dict[str, Any]:
    """Latest structure and regime for every timeframe plus the recent M15 regime path."""
    out: dict[str, Any] = {}
    for tf, frame in (
        (Timeframe.H4, frames.h4),
        (Timeframe.H1, frames.h1),
        (Timeframe.M15, frames.m15),
        (Timeframe.M5, frames.m5),
    ):
        ctx = build_context(frame.tail(1500), tf)
        last = ctx.row(ctx.height - 1, named=True)
        out[tf.value] = {
            "timestamp": last["timestamp"],
            "regime": last["regime"],
            "trend": last["trend"],
            "bos": last["bos"],
            "choch": last["choch"],
            "support": last["support"],
            "resistance": last["resistance"],
        }
    m15 = build_context(frames.m15.tail(1500), Timeframe.M15).tail(96)
    out["recent_m15_regimes"] = m15.select("timestamp", "regime").to_dicts()
    return json_dict(out)


def _path(values: np.ndarray) -> list[float]:
    return [float(x) for x in np.concatenate([[0.0], np.cumsum(values)])]


def analogue_view(frames: MarketFrames, at: datetime, k: int = 10) -> dict[str, Any]:
    """Current pattern versus its top historical analogues, normalised, with what followed.

    The "what followed" path is for DISPLAY only; it never feeds a model input (ADR-0013).
    """
    bars = frames.m15.filter(pl.col("timestamp") <= at - Timeframe.M15.delta)
    if bars.height == 0:
        return {"available": False, "reason": "no bars before that time", "matches": []}
    values = pattern_values(bars)
    ctx = build_context(bars, Timeframe.M15)
    closed = ctx.filter(pl.col("available_at") <= at)
    q = closed.height - 1
    if q < WINDOW - 1 or not window_validity(values, WINDOW)[q - WINDOW + 1]:
        return {"available": False, "reason": "not enough valid history", "matches": []}
    result = PatternIndex(values, SearchConfig(window=WINDOW, horizon=60, k=k)).search(q)
    ret = values[:, 0]  # close-to-close change in ATR units
    atr = closed["atr_14"].fill_null(float("nan")).to_numpy()
    close = bars["close"].to_numpy()
    matches = []
    for m in result.matches:
        e = m.end_index
        after = (
            (close[e + 1 : e + 1 + OUTCOME_BARS] - close[e]) / atr[e]
            if e + OUTCOME_BARS < len(close)
            else []
        )
        matches.append(
            {
                "rank": m.rank,
                "end_time": bars["timestamp"][e],
                "distance": m.distance,
                "pattern_path": _path(ret[e - WINDOW + 1 : e + 1]),
                "outcome_path": [0.0, *[float(x) for x in after]],
            }
        )
    return json_dict(
        {
            "available": True,
            "at": closed["available_at"][q],
            "window": WINDOW,
            "outcome_bars": OUTCOME_BARS,
            "current_path": _path(ret[q - WINDOW + 1 : q + 1]),
            "candidates": result.n_candidates,
            "best_distance": result.best_distance,
            "median_distance": result.median_distance,
            "matches": matches,
        }
    )


def backtest_records(registry: ExperimentRegistry) -> list[dict[str, Any]]:
    """Summary rows of every recorded backtest, model and analogue-study run."""
    rows: list[dict[str, Any]] = []
    for family in ("backtest", "model", "analogue-study"):
        for rec in registry.list(family):
            metrics = rec.metrics
            verdict = metrics.get("verdict", {})
            rows.append(
                {
                    "id": rec.id,
                    "family": rec.family,
                    "name": rec.name,
                    "period": rec.period,
                    "created_at": rec.created_at,
                    "passed": metrics.get("passed", verdict.get("passed")),
                    "trades": metrics.get("trades", metrics.get("metrics", {}).get("trade_count")),
                }
            )
    return json_list(rows)


def model_records(models_dir: Path) -> list[dict[str, Any]]:
    """Metadata of stored model artifacts (never loads the pickled models)."""
    rows: list[dict[str, Any]] = []
    if models_dir.exists():
        for meta_path in sorted(models_dir.glob("*/*/metadata.json")):
            meta = load_artifact_metadata(meta_path.parent)
            rows.append(
                {
                    k: meta[k]
                    for k in ("name", "version", "feature_version", "trained_at", "metrics")
                }
            )
    return json_list(rows)
