"""End-to-end data parity: what the XAU EDGE chart shows vs the FTMO terminal's own bars.

    uv run --extra mt5 python scripts/verify_visual_parity.py [--samples 40] [--write]

The page draws exactly the bars that ``/md/XAUUSD/bars`` returns. For sampled CLOSED bars of every
timeframe this script fetches the same bar from the terminal through an INDEPENDENT path (raw
``copy_rates_range`` with the broker time computed by zoneinfo, New York + 7 h, not by the project's
BrokerClock) and compares timestamp, open, high, low, close and tick volume. The terminal's chart is
drawn from the same terminal data, so this is the numeric equivalent of comparing the two charts
bar by bar. (The terminal window itself is deliberately not screen-captured: it can show account
details.) The API must be running (scripts/run_market_stack.py).
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from xau_edge.domain.timeframe import Timeframe  # noqa: E402
from xau_edge.market_data.mt5.runtime import DEFAULT_TERMINAL, open_feed  # noqa: E402

OUT = ROOT / "docs" / "reports" / "mt5-visual-parity.json"
NY = ZoneInfo("America/New_York")


def server_wall(utc_dt: datetime) -> datetime:
    """Broker server wall clock = New York wall clock + 7 hours (independent of BrokerClock)."""
    return utc_dt.astimezone(NY).replace(tzinfo=None) + timedelta(hours=7)


def api_bars(api: str, tf: str, limit: int) -> list[dict[str, Any]]:
    url = f"{api}/md/XAUUSD/bars?timeframe={tf}&limit={limit}&include_forming=false"
    with urllib.request.urlopen(url, timeout=30) as response:  # noqa: S310 - local API
        return json.loads(response.read())["bars"]  # type: ignore[no-any-return]


def sample(bars: list[dict[str, Any]], count: int) -> list[dict[str, Any]]:
    """The newest 3 closed bars plus evenly spaced older ones (deterministic)."""
    if len(bars) <= count:
        return bars
    step = max(1, (len(bars) - 3) // (count - 3))
    return bars[-3:] + bars[: len(bars) - 3 : step][: count - 3]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--terminal-path", default=DEFAULT_TERMINAL)
    parser.add_argument("--api", default="http://127.0.0.1:8000")
    parser.add_argument("--samples", type=int, default=40)
    parser.add_argument("--limit", type=int, default=5000)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    report: dict[str, Any] = {"checked_at": datetime.now(UTC).isoformat(), "timeframes": {}}
    ok = True
    with open_feed(args.terminal_path) as feed:
        client = feed.client
        mapping = feed.discover_symbol("XAUUSD")
        feed.select(mapping.broker_symbol)
        for tf in Timeframe:
            constant = getattr(client, f"TIMEFRAME_{tf.value}")
            picked = sample(api_bars(args.api, tf.value, args.limit), args.samples)
            rows: list[dict[str, Any]] = []
            mismatches = 0
            for bar in picked:
                utc_dt = datetime.fromisoformat(bar["time"])
                wall = server_wall(utc_dt)
                want = int(wall.replace(tzinfo=UTC).timestamp())
                span = wall + timedelta(minutes=tf.minutes) - timedelta(seconds=1)
                # a NAIVE datetime would be read as this PC's local time; label the server wall clock UTC
                raw = client.copy_rates_range(
                    mapping.broker_symbol,
                    constant,
                    wall.replace(tzinfo=UTC),
                    span.replace(tzinfo=UTC),
                )
                found = [] if raw is None else [r for r in raw if int(r["time"]) == want]
                terminal = found[0] if found else None
                if terminal is None:
                    rows.append({"time_utc": bar["time"], "result": "NOT_IN_TERMINAL_CACHE"})
                    continue
                same_time = int(terminal["time"]) == want
                same = (
                    same_time
                    and abs(float(terminal["open"]) - bar["open"]) < 1e-9
                    and abs(float(terminal["high"]) - bar["high"]) < 1e-9
                    and abs(float(terminal["low"]) - bar["low"]) < 1e-9
                    and abs(float(terminal["close"]) - bar["close"]) < 1e-9
                    and int(terminal["tick_volume"]) == bar["tick_volume"]
                )
                mismatches += 0 if same else 1
                rows.append(
                    {
                        "time_utc": bar["time"],
                        "broker_time": wall.isoformat(),
                        "terminal_ohlc": [
                            float(terminal[k]) for k in ("open", "high", "low", "close")
                        ],
                        "xau_edge_ohlc": [bar["open"], bar["high"], bar["low"], bar["close"]],
                        "terminal_tick_volume": int(terminal["tick_volume"]),
                        "xau_edge_tick_volume": bar["tick_volume"],
                        "result": "MATCH" if same else "MISMATCH",
                    }
                )
            compared = [r for r in rows if r["result"] in ("MATCH", "MISMATCH")]
            report["timeframes"][tf.value] = {
                "sampled": len(rows),
                "compared": len(compared),
                "mismatches": mismatches,
                "not_in_terminal_cache": len(rows) - len(compared),
                "rows": rows,
            }
            ok = ok and mismatches == 0 and len(compared) > 0
            print(tf.value, "compared", len(compared), "mismatches", mismatches)
    report["ok"] = ok
    if args.write:
        OUT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
