"""Read-only MT5 probe: M1 and tick history depth and symbol availability (P0, Class D).

Connects to the local terminal and REFUSES unless the logged-in account is a DEMO account. Calls no
trading function and prints/stores no account identifier, balance or login: only counts, years and
symbol names. Output: ``docs/research/edge-program-v2/mt5-probe.json``.

    uv run --extra mt5 python scripts/probe_mt5_depth.py [--write]
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from xau_edge.market_data.mt5.source import load_mt5_module  # noqa: E402

DEFAULT_TERMINAL = r"C:\Program Files\FTMO Global Markets MT5 Terminal\terminal64.exe"
OUT = ROOT / "docs" / "research" / "edge-program-v2" / "mt5-probe.json"
WANTED = (
    "XAUUSD", "XAGUSD", "XAUEUR", "XAUAUD", "EURUSD", "USDJPY", "GBPUSD", "AUDUSD", "USDCHF",
    "USDX", "DXY", "US500", "US100", "US30", "USOIL", "UKOIL", "BTCUSD", "GER40", "VIX",
)  # fmt: skip


TICK_SAMPLES = (
    (2025, 3),
    (2023, 3),
    (2022, 3),
    (2021, 9),
    (2021, 3),
    (2020, 3),
    (2019, 3),
    (2015, 3),
)


def probe_m1(mt5: Any, symbol: str) -> dict[int, int | str]:
    """Bars of one trading week per year; 0 or 1 means the terminal could not serve that history."""
    out: dict[int, int | str] = {}
    for year in (2025, 2022, 2018, 2012):
        start = datetime(year, 3, 6, tzinfo=UTC)
        best = 0
        for _ in range(2):
            rates = mt5.copy_rates_range(symbol, mt5.TIMEFRAME_M1, start, start + timedelta(days=4))
            best = max(best, 0 if rates is None else len(rates))
            if best > 500:
                break
            time.sleep(2)
        out[year] = best if best > 1 else "INCONCLUSIVE (terminal served at most 1 bar)"
    return out


def probe_ticks(mt5: Any, symbol: str) -> dict[str, int]:
    """Ticks in a 5-minute window at several dates (0 means no tick history that far back)."""
    out: dict[str, int] = {}
    for year, month in TICK_SAMPLES:
        start = datetime(year, month, 7, 10, 0, tzinfo=UTC)
        ticks = mt5.copy_ticks_range(
            symbol, start, start + timedelta(minutes=5), mt5.COPY_TICKS_ALL
        )
        out[f"{year}-{month:02d}"] = 0 if ticks is None else len(ticks)
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--terminal-path", default=DEFAULT_TERMINAL)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    mt5 = load_mt5_module()
    if not mt5.initialize(path=args.terminal_path, timeout=90000):
        print(f"initialize failed: {mt5.last_error()}")
        return 2
    try:
        account = mt5.account_info()
        if account is None or account.trade_mode != mt5.ACCOUNT_TRADE_MODE_DEMO:
            print("REFUSING: the connected account is not a DEMO account (or none is logged in).")
            return 3
        names = {s.name for s in (mt5.symbols_get() or [])}
        present = sorted(n for n in WANTED if n in names)
        extra_gold = sorted(n for n in names if n.upper().startswith(("XAU", "GOLD")))
        result: dict[str, Any] = {
            "class": "D (data availability probe; no market outcome used)",
            "probed_at": datetime.now(UTC).isoformat(),
            "symbols_total": len(names),
            "wanted_present": present,
            "wanted_missing": sorted(set(WANTED) - set(present)),
            "gold_like_symbols": extra_gold,
            "m1_bars_one_week_per_year": {},
            "ticks_five_minutes_per_sample": {},
        }
        for symbol in ("XAUUSD",):
            if symbol in names:
                mt5.symbol_select(symbol, True)
                result["m1_bars_one_week_per_year"][symbol] = probe_m1(mt5, symbol)
                result["ticks_five_minutes_per_sample"][symbol] = probe_ticks(mt5, symbol)
        print(json.dumps(result, indent=2))
        if args.write:
            OUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
            print(f"wrote {OUT.name}")
        return 0
    finally:
        mt5.shutdown()


if __name__ == "__main__":
    raise SystemExit(main())
