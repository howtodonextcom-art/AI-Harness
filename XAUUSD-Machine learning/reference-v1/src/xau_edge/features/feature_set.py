"""Versioned feature set built from a validated bar frame, stored keyed by dataset id.

``gap_before`` marks a bar that does not directly follow the previous row (weekend, daily break,
holiday or missing data), so a consumer can tell a one-bar return from one that spans a gap.

Row ``i`` describes the bar opening at ``timestamp`` and is usable only from ``available_at``
(the bar's close). Every value depends on bars ``0..i`` only; a test removes later bars and
requires identical earlier rows. Rows are consecutive bars: weekend and holiday gaps are not
bridged with synthetic bars, so an indicator window can span a closure.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import stat
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from typing import Final

import numpy as np
import polars as pl
from numpy.typing import NDArray
from pydantic import BaseModel, ConfigDict, Field

from xau_edge.domain.bars import REQUIRED_COLUMNS
from xau_edge.domain.timeframe import Timeframe
from xau_edge.features import indicators as ind
from xau_edge.features.candles import candle_geometry
from xau_edge.features.sessions import session_features
from xau_edge.features.volume import volume_change, volume_zscore
from xau_edge.market_data.store import dataframe_sha256, is_safe_name
from xau_edge.observability import log_event

FEATURE_SET_VERSION: Final = "1"
_LOG = logging.getLogger(__name__)
_ID_SAFE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


class FeatureConfig(BaseModel):
    """Parameters of the feature set. Any change yields a different ``feature_id``."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    ema_periods: tuple[int, ...] = (9, 20, 50, 200)
    return_windows: tuple[int, ...] = (5, 10, 20)
    rsi_period: int = Field(default=14, ge=2)
    atr_period: int = Field(default=14, ge=1)
    adx_period: int = Field(default=14, ge=2)
    macd: tuple[int, int, int] = (12, 26, 9)
    stochastic: tuple[int, int, int] = (14, 3, 3)
    bollinger_period: int = Field(default=20, ge=1)
    bollinger_std: float = Field(default=2.0, ge=0)
    volatility_window: int = Field(default=20, ge=2)
    volume_window: int = Field(default=20, ge=2)


def _canonical(config: FeatureConfig) -> str:
    return json.dumps(config.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))


def feature_id(dataset_id: str, timeframe: Timeframe, config: FeatureConfig | None = None) -> str:
    """Stable id of a feature set: version, dataset, timeframe and parameters."""
    cfg = config or FeatureConfig()
    raw = f"{FEATURE_SET_VERSION}|{dataset_id}|{timeframe.value}|{_canonical(cfg)}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def check_bars(bars: pl.DataFrame) -> None:
    missing = [c for c in REQUIRED_COLUMNS if c not in bars.columns]
    if missing:
        msg = f"missing column(s): {', '.join(missing)}"
        raise ValueError(msg)
    if bars.height == 0:
        msg = "cannot build features from an empty frame"
        raise ValueError(msg)
    dtype = bars.schema["timestamp"]
    if not isinstance(dtype, pl.Datetime) or dtype.time_zone != "UTC":
        msg = f"timestamp must be Datetime in UTC, got {dtype}"
        raise ValueError(msg)
    ts = bars["timestamp"]
    if bars.height > 1 and not (ts.diff().drop_nulls() > timedelta(0)).all():
        msg = "timestamps must be strictly increasing (sorted and unique); validate the data first"
        raise ValueError(msg)


def _col(name: str, values: NDArray[np.float64]) -> pl.Series:
    return pl.Series(name, values, dtype=pl.Float64, nan_to_null=True)


def build_features(
    bars: pl.DataFrame, timeframe: Timeframe, config: FeatureConfig | None = None
) -> pl.DataFrame:
    """Compute the feature frame for ``bars`` (sorted, unique, UTC, validated upstream)."""
    cfg = config or FeatureConfig()
    check_bars(bars)
    o, h, lo, c = (bars[k].to_numpy() for k in ("open", "high", "low", "close"))
    volume = bars["tick_volume"].to_numpy().astype(np.float64)
    ts = bars["timestamp"]

    atr = ind.atr(h, lo, c, cfg.atr_period)
    geometry = candle_geometry(o, h, lo, c, atr)
    adx = ind.adx(h, lo, c, cfg.adx_period)
    macd = ind.macd(c, *cfg.macd)
    stoch = ind.stochastic(h, lo, c, *cfg.stochastic)
    boll = ind.bollinger(c, cfg.bollinger_period, cfg.bollinger_std)

    columns: list[pl.Series] = [
        ts.alias("timestamp"),
        ts.dt.offset_by(f"{timeframe.minutes}m").alias("available_at"),
        (ts.diff() > timeframe.delta).fill_null(value=False).alias("gap_before"),
        _col("ret_1", ind.simple_returns(c)),
        _col("log_ret_1", ind.log_returns(c)),
    ]
    columns += [_col(f"ret_{w}", ind.rolling_returns(c, w)) for w in cfg.return_windows]
    columns += [_col(f"ema_{p}", ind.ema(c, p)) for p in cfg.ema_periods]
    n = cfg.adx_period
    columns += [
        _col(f"adx_{n}", adx.adx),
        _col(f"plus_di_{n}", adx.plus_di),
        _col(f"minus_di_{n}", adx.minus_di),
        _col(f"rsi_{cfg.rsi_period}", ind.rsi(c, cfg.rsi_period)),
        _col("macd", macd.macd),
        _col("macd_signal", macd.signal),
        _col("macd_hist", macd.histogram),
        _col("stoch_k", stoch.k),
        _col("stoch_d", stoch.d),
        _col(f"atr_{cfg.atr_period}", atr),
        _col("bb_upper", boll.upper),
        _col("bb_middle", boll.middle),
        _col("bb_lower", boll.lower),
        _col(f"vol_{cfg.volatility_window}", ind.rolling_volatility(c, cfg.volatility_window)),
        _col("range_atr", geometry.range_to_atr),
        _col("body_size", geometry.body_size),
        _col("upper_wick", geometry.upper_wick),
        _col("lower_wick", geometry.lower_wick),
        _col("body_range", geometry.body_to_range),
        _col("body_atr", geometry.body_to_atr),
        _col("upper_wick_atr", geometry.upper_wick_to_atr),
        _col("lower_wick_atr", geometry.lower_wick_to_atr),
        bars["tick_volume"].alias("tick_volume"),
        _col("volume_zscore", volume_zscore(volume, cfg.volume_window)),
        _col("volume_change", volume_change(volume)),
    ]
    frame = pl.DataFrame(columns)
    return frame.hstack(session_features(ts))


@dataclass(frozen=True)
class FeatureSetRef:
    """Reference to a stored feature set."""

    path: Path
    feature_id: str
    dataset_id: str
    symbol: str
    timeframe: Timeframe
    rows: int
    sha256: str


class FeatureStore:
    """Write-once store of feature frames under ``<root>/<symbol>/<timeframe>/<feature_id>``."""

    def __init__(self, root: Path | str) -> None:
        self.root = Path(root)

    def write(
        self,
        frame: pl.DataFrame,
        *,
        symbol: str,
        timeframe: Timeframe,
        dataset_id: str,
        config: FeatureConfig | None = None,
    ) -> FeatureSetRef:
        """Store ``frame``; identical content is a no-op, different content raises."""
        if not is_safe_name(symbol):
            msg = f"unsafe symbol name {symbol!r}"
            raise ValueError(msg)
        if not _ID_SAFE.fullmatch(dataset_id) or not is_safe_name(dataset_id):
            msg = f"unsafe dataset_id {dataset_id!r}"
            raise ValueError(msg)
        fid = feature_id(dataset_id, timeframe, config)
        directory = self.root / symbol / timeframe.value
        path = directory / f"{fid}.parquet"
        digest = dataframe_sha256(frame)
        ref = FeatureSetRef(path, fid, dataset_id, symbol, timeframe, frame.height, digest)
        if path.exists():
            if dataframe_sha256(pl.read_parquet(path)) != digest:
                msg = f"{path} exists with different content; feature sets are immutable"
                raise ValueError(msg)
            return ref
        directory.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(path.name + ".tmp")
        frame.write_parquet(tmp)
        tmp.rename(path)
        path.chmod(stat.S_IREAD)
        path.with_suffix(".meta.json").write_text(
            json.dumps(
                {
                    "feature_id": fid,
                    "version": FEATURE_SET_VERSION,
                    "dataset_id": dataset_id,
                    "symbol": symbol,
                    "timeframe": timeframe.value,
                    "rows": frame.height,
                    "sha256": digest,
                    "config": json.loads(_canonical(config or FeatureConfig())),
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        log_event(
            _LOG,
            "features.write",
            feature_id=fid,
            dataset_id=dataset_id,
            symbol=symbol,
            timeframe=timeframe.value,
            rows=frame.height,
        )
        return ref

    def read(self, ref: FeatureSetRef) -> pl.DataFrame:
        """Read a stored feature set, verifying its location and content hash."""
        if not ref.path.resolve().is_relative_to(self.root.resolve()):
            msg = f"{ref.path} is outside the store root {self.root}"
            raise ValueError(msg)
        frame = pl.read_parquet(ref.path)
        if dataframe_sha256(frame) != ref.sha256:
            msg = f"{ref.path} no longer matches its recorded hash"
            raise ValueError(msg)
        return frame
