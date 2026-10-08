"""Read-only: fetch MT5 history that predates the local raw store (edge program, T1.2).

Uses the allowlisted read-only client (market data only) and refuses anything but a DEMO account.
It never reads ``.env`` (settings are built with ``_env_file=None``), never logs in with explicit
credentials (the terminal's own session is used) and never prints account details.

Fetched bars go to a SEPARATE immutable store (``data/research_history``) so that the live bot's
catalog and the dataset ids of earlier experiments are untouched. Each timeframe is stored as
``[earliest available, --end)``; a manifest with row counts, first/last bars and content hashes is
written next to the research notes. Nothing about returns or prices is computed here.

Usage: uv run --extra mt5 python scripts/fetch_history.py
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import polars as pl

from xau_edge.domain.bars import BarRequest
from xau_edge.domain.timeframe import Timeframe
from xau_edge.experiments.history import fetch_back
from xau_edge.market_data.catalog import DatasetCatalog
from xau_edge.market_data.mt5.source import Mt5BarSource, Mt5Settings, load_mt5_module
from xau_edge.market_data.profiles import BrokerProfile
from xau_edge.market_data.store import RawStore
from xau_edge.market_data.validators import validate_bars

DEFAULT_TERMINAL = r"C:\Program Files\FTMO Global Markets MT5 Terminal\terminal64.exe"
SOURCE = "mt5-ftmo-demo-history"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--terminal-path", default=DEFAULT_TERMINAL)
    parser.add_argument("--symbol", default="XAUUSD")
    parser.add_argument("--end", default="2025-05-01")
    parser.add_argument("--profile", default="configs/brokers/ftmo_demo.yaml")
    parser.add_argument("--root", default="data/research_history")
    parser.add_argument("--manifest", default="docs/research/edge-program/data-manifest.json")
    args = parser.parse_args()

    profile = BrokerProfile.from_yaml(args.profile)
    end = datetime.fromisoformat(args.end).replace(tzinfo=UTC)
    settings = Mt5Settings(  # type: ignore[call-arg]
        _env_file=None,
        terminal_path=Path(args.terminal_path),
        broker_timezone=profile.clock.token,
    )
    source = Mt5BarSource(load_mt5_module(), settings)
    source.connect()  # DEMO-account guard inside
    store = RawStore(args.root)
    manifest: dict[str, Any] = {"generated_at": datetime.now(UTC).isoformat(), "end": args.end}
    try:
        for tf in Timeframe:

            def fetch(start: datetime, stop: datetime, tf: Timeframe = tf) -> pl.DataFrame:
                return source.fetch_bars(
                    BarRequest(symbol=args.symbol, timeframe=tf, start=start, end=stop)
                )

            bars = fetch_back(fetch, end=end)
            if bars.height == 0:
                manifest[tf.value] = {"rows": 0}
                print(f"{tf.value}: nothing available")
                continue
            ds = store.write(
                bars, symbol=args.symbol, timeframe=tf, source=SOURCE, fetched_at=datetime.now(UTC)
            )
            report = validate_bars(bars, tf, symbol=args.symbol, config=profile.validation)
            issues = [
                {"code": i.code.value, "severity": i.severity.value, "count": i.count}
                for i in report.issues
            ]
            loaded = DatasetCatalog(args.root).load(args.symbol, tf)
            manifest[tf.value] = {
                "rows": bars.height,
                "first": bars["timestamp"].min().isoformat(),  # type: ignore[union-attr]
                "last": bars["timestamp"].max().isoformat(),  # type: ignore[union-attr]
                "sha256": ds.sha256,
                "dataset_id": loaded.dataset_id,
                "validation_passed": report.passed,
                "issues": issues,
            }
            print(
                f"{tf.value}: {bars.height} rows {manifest[tf.value]['first']} .. "
                f"{manifest[tf.value]['last']}, validation {'ok' if report.passed else 'issues'}"
            )
    finally:
        source.close()
    out = Path(args.manifest)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
