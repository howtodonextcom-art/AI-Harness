"""Safe diagnosis of the local MT5 environment (OS, Python, package, terminals, connection).

Never prints a login, password, balance or token. JSON on stdout; exit code 0 when a working,
connected DEMO terminal was found, 2 otherwise.

    uv run --extra mt5 python scripts/diagnose_mt5_environment.py [--no-connect] [--terminal-path P]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from xau_edge.market_data.mt5.diagnostics import environment_report  # noqa: E402
from xau_edge.market_data.mt5.runtime import DEFAULT_TERMINAL, open_feed  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--terminal-path", default=None)
    parser.add_argument("--no-connect", action="store_true")
    args = parser.parse_args()
    preferred = Path(args.terminal_path or DEFAULT_TERMINAL)
    report = environment_report(preferred=preferred)
    report["connection"] = {"attempted": False}
    ok = False
    selected = report["selected_terminal"]
    if not args.no_connect and report["package"]["installed"] and selected:
        try:
            with open_feed(selected) as feed:
                facts = feed.facts()
                names = []
                try:
                    mapping = feed.discover_symbol("XAUUSD")
                    names = [mapping.broker_symbol]
                except RuntimeError as exc:
                    report["connection"]["symbol_error"] = str(exc)
                report["connection"] |= {
                    "attempted": True,
                    "connected": facts.connected,
                    "demo_account": facts.demo,
                    "server": facts.server,
                    "terminal_build": facts.build,
                    "terminal_version": list(facts.version) if facts.version else None,
                    "algorithmic_trading_enabled": facts.trade_allowed,
                    "max_bars_in_chart": facts.max_bars,
                    "xau_symbols": names,
                }
                ok = bool(facts.connected and facts.demo)
        except Exception as exc:
            report["connection"] |= {"attempted": True, "error": f"{type(exc).__name__}: {exc}"}
    print(json.dumps(report, indent=2, default=str))
    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
