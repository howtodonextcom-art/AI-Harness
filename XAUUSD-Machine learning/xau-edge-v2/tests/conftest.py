from __future__ import annotations

import json
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path

import polars as pl
import pytest
from fastapi.testclient import TestClient

from xau_edge_v2.api.app import create_app
from xau_edge_v2.config import Settings
from xau_edge_v2.domain.contract import Timeframe


def write_series(  # noqa: PLR0913 - a test data factory
    root: Path,
    tf: Timeframe,
    start: datetime,
    count: int,
    *,
    step_minutes: int | None = None,
    base: float = 100.0,
) -> list[datetime]:
    """Closed bars every ``step`` minutes from ``start``, split into monthly files (like V1)."""
    step = step_minutes if step_minutes is not None else tf.seconds // 60
    times = [start + timedelta(minutes=step * i) for i in range(count)]
    frame = pl.DataFrame(
        {
            "timestamp": times,
            "open": [base + i * 0.01 for i in range(count)],
            "high": [base + i * 0.01 + 1.0 for i in range(count)],
            "low": [base + i * 0.01 - 1.0 for i in range(count)],
            "close": [base + i * 0.01 + 0.5 for i in range(count)],
            "tick_volume": [10 + i % 7 for i in range(count)],
            "spread": [20 + i % 5 for i in range(count)],
            "real_volume": [0] * count,
        }
    ).with_columns(
        pl.col("timestamp").dt.replace_time_zone("UTC"),
        pl.col("tick_volume").cast(pl.Int64),
        pl.col("spread").cast(pl.Int64),
        pl.col("real_volume").cast(pl.Int64),
    )
    folder = root / "XAUUSD" / tf.value
    folder.mkdir(parents=True, exist_ok=True)
    keyed = frame.with_columns(pl.col("timestamp").dt.strftime("%Y-%m").alias("_m"))
    for month in keyed["_m"].unique().to_list():
        part = keyed.filter(pl.col("_m") == month).drop("_m")
        part.write_parquet(folder / f"{month}.parquet")
    return times


def write_store(root: Path, *, minutes: int = 5, last_open: datetime | None = None) -> Path:
    """A tiny store shaped like the shared one (M1/M5/H1 ending at ``last_open``)."""
    end = last_open or (datetime.now(UTC).replace(second=0, microsecond=0) - timedelta(minutes=2))
    for tf, step in ((Timeframe.M1, 1), (Timeframe.M5, 5), (Timeframe.H1, 60)):
        start = end - timedelta(minutes=step * (minutes - 1))
        write_series(root, tf, start, minutes, step_minutes=step)
    return root


def write_live(
    root: Path,
    *,
    at: datetime | None = None,
    quote_age_s: float = 1.0,
    file_age_s: float = 1.0,
    **spec: object,
) -> None:
    now = at or datetime.now(UTC)
    payload = {
        "updated_at": (now - timedelta(seconds=file_age_s)).isoformat(),
        "quote": {
            "bid": 4165.43, "ask": 4165.78, "mid": 4165.605, "spread_points": 35.0,
            "spread_price": 0.35, "timestamp": (now - timedelta(seconds=quote_age_s)).isoformat(),
        },
        "forming": {},
        "symbol_spec": {
            "digits": 2, "point": 0.01, "trade_tick_size": 0.01, "trade_tick_value": 1.0,
            "trade_contract_size": 100.0, "trade_stops_level": 0, "trade_freeze_level": 0,
            "volume_min": 0.01, "volume_step": 0.01, "volume_max": 100.0, **spec,
        },
    }  # fmt: skip
    (root / "live.json").write_text(json.dumps(payload), encoding="utf-8")


@pytest.fixture
def store(tmp_path: Path) -> Path:
    root = write_store(tmp_path / "market")
    write_live(root)
    return root


@pytest.fixture
def web_dist(tmp_path: Path) -> Path:
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<!doctype html><title>x</title><div id=root></div>")
    (dist / "assets" / "app-abc123.js").write_text("a" * 5000)
    return dist


@pytest.fixture
def make_client(tmp_path: Path, store: Path, web_dist: Path) -> Callable[..., TestClient]:
    def _make(**overrides: object) -> TestClient:
        base: dict[str, object] = {
            "data_root": store,
            "web_dist": web_dist,
            "log_dir": tmp_path / "logs",
            "heartbeat_seconds": 0.05,
            "paper_db": tmp_path / "paper.sqlite3",
            "engine_enabled": False,
            "auto_paper": False,
            "backup_mirrors": [],
            "alerts_enabled": False,
        }
        base.update(overrides)
        return TestClient(create_app(Settings(**base)))  # type: ignore[arg-type]

    return _make
