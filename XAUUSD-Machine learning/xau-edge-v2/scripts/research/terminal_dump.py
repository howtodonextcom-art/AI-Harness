"""READ-ONLY dump of the broker terminal's own XAUUSD H1/H4/D1 history (independent re-fetch).

Used by the data-provenance forensic audit. It calls ``copy_rates_range`` only: no order function, no
account information, no login, no terminal setting is touched. Run it with an interpreter that has
the ``MetaTrader5`` package (V1's venv), NOT from the V2 package (V2 never imports it, ADR-V2-008):

    <V1>/.venv/Scripts/python.exe scripts/research/terminal_dump.py --out data/research/terminal_dump

Times are the terminal SERVER time (the broker's clock) stored as epoch seconds, untouched; the
comparison script derives the offset to UTC from the bars themselves.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import MetaTrader5 as mt5  # noqa: N813 - forensic tool, outside the V2 package

FRAMES = {"H1": mt5.TIMEFRAME_H1, "H4": mt5.TIMEFRAME_H4, "D1": mt5.TIMEFRAME_D1}
FORBIDDEN = ("order_send", "order_check", "positions_get", "orders_get", "account_info", "login")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--symbol", default="XAUUSD")
    ap.add_argument(
        "--terminal-path",
        default="",
        help="attach to THIS terminal (default: the default one, which may be MetaQuotes-Demo, not FTMO)",
    )
    ap.add_argument("--from-year", type=int, default=2004)
    a = ap.parse_args()
    ok = mt5.initialize(path=a.terminal_path) if a.terminal_path else mt5.initialize()
    if not ok:
        sys.exit(f"terminal not reachable: {mt5.last_error()}")
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    now = datetime.now(UTC)
    summary: dict[str, dict[str, int]] = {}
    for name, tf in FRAMES.items():
        rows: list[list[float]] = []
        for year in range(a.from_year, now.year + 1):
            start, end = datetime(year, 1, 1, tzinfo=UTC), datetime(year + 1, 1, 1, tzinfo=UTC)
            got = mt5.copy_rates_range(a.symbol, tf, start, end)
            if got is None:
                continue
            rows += [
                [int(x["time"]), float(x["open"]), float(x["high"]), float(x["low"]), float(x["close"]),
                 int(x["tick_volume"]), int(x["spread"]), int(x["real_volume"])]
                for x in got
            ]  # fmt: skip
        rows.sort()
        (out / f"{a.symbol}_{name}.json").write_text(json.dumps(rows), encoding="utf-8")
        summary[name] = {
            "rows": len(rows),
            "first": rows[0][0] if rows else 0,
            "last": rows[-1][0] if rows else 0,
        }
    info = mt5.terminal_info()._asdict()
    bases = Path(info["data_path"]) / "bases"
    provenance = {
        "terminal": {k: info[k] for k in ("company", "path", "build", "maxbars")},
        "server_folders": sorted(
            p.name
            for p in bases.iterdir()
            if p.is_dir() and p.name not in ("Custom", "Default", "signals")
        ),
    }
    mt5.shutdown()
    (out / "provenance.json").write_text(json.dumps(provenance, indent=1), encoding="utf-8")
    (out / "dump_meta.json").write_text(
        json.dumps({"taken_at": now.isoformat(), "symbol": a.symbol, "summary": summary}, indent=1),
        encoding="utf-8",
    )
    print(json.dumps(summary))


if __name__ == "__main__":
    main()
