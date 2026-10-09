"""Probe the MT5 data path end to end on the DEMO terminal (market data only, no order functions).

    uv run --extra mt5 python scripts/mt5_connection_probe.py [--write] [--no-tick-depth]

Output: structured JSON (terminal, server, symbol, per-timeframe availability and depth, tick depth,
bid/ask, volume semantics). Fails closed (exit 3) on a non-DEMO account.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from xau_edge.market_data.mt5.diagnostics import connection_probe  # noqa: E402
from xau_edge.market_data.mt5.runtime import DEFAULT_TERMINAL, open_feed  # noqa: E402

OUT = ROOT / "docs" / "reports" / "mt5-connection-probe.json"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--terminal-path", default=DEFAULT_TERMINAL)
    parser.add_argument("--symbol", default="XAUUSD")
    parser.add_argument("--no-tick-depth", action="store_true")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    with open_feed(args.terminal_path) as feed:
        report = connection_probe(
            feed,
            canonical=args.symbol,
            terminal_path=args.terminal_path,
            with_tick_depth=not args.no_tick_depth,
        )
    text = json.dumps(report, indent=2, default=str)
    print(text)
    if args.write:
        OUT.write_text(text + "\n", encoding="utf-8")
    return 3 if not report.get("demo_account") else 0


if __name__ == "__main__":
    raise SystemExit(main())
