"""Print the signal for the latest closed M15 bar of the local dataset (research only).

Usage: ``uv run python scripts/current_signal.py [--at 2026-10-07T12:00:00Z]``
The answer is WAIT unless the evidence gate is open (a configuration validated on every period).
"""

from __future__ import annotations

import argparse
from datetime import UTC, datetime

from xau_edge.domain.timeframe import Timeframe
from xau_edge.experiments.registry import ExperimentRegistry
from xau_edge.market_data.catalog import DatasetCatalog
from xau_edge.observability import configure_logging
from xau_edge.signals.engine import MarketFrames, generate_signal


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default="data/raw")
    parser.add_argument("--at", default=None, help="UTC decision time, e.g. 2026-10-07T12:00:00Z")
    args = parser.parse_args()
    configure_logging("WARNING")

    catalog = DatasetCatalog(args.root)
    frames = MarketFrames(
        *(
            catalog.load("XAUUSD", tf).frame
            for tf in (Timeframe.M5, Timeframe.M15, Timeframe.H1, Timeframe.H4)
        )
    )
    if args.at:
        at = datetime.fromisoformat(args.at.replace("Z", "+00:00")).astimezone(UTC)
    else:
        latest = frames.m15["timestamp"].max()
        if not isinstance(latest, datetime):
            msg = "no M15 data loaded"
            raise SystemExit(msg)
        at = latest + Timeframe.M15.delta
    registry = ExperimentRegistry("experiments/runs")
    signal = generate_signal(frames, at, registry)
    print(signal.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
