# ruff: noqa - one-off read-only MT5 probe for V3_RESEARCH_FOUNDATION_AND_HUMAN_DECISION.md
"""Read-only probe: are EURUSD / USDJPY / XAGUSD on the same broker terminal, and how deep is their history?

Market data only. No order function is imported or called; terminal settings are not changed.
Every step prints before it runs, so a hang is visible.

    uv run --extra mt5 python docs\\research\\edge-program-v3\\foundation\\cross_asset_probe.py
"""

import json
import os
import sys
from datetime import datetime, timezone

import MetaTrader5 as mt5

TERMINAL = r"C:\Program Files\FTMO Global Markets MT5 Terminal\terminal64.exe"
SYMBOLS = ["XAUUSD", "EURUSD", "USDJPY", "XAGUSD"]
WINDOWS = [
    2005,
    2011,
    2015,
    2019,
    2022,
    2025,
]  # 3 March, 3 days: does the terminal return bars in that era?
OUT = os.path.join(os.path.dirname(__file__), "cross_asset_probe.json")


def step(msg: str) -> None:
    print(f"[{datetime.now(timezone.utc).strftime('%H:%M:%S')}] {msg}", flush=True)


def main() -> int:
    step("initialize")
    if not mt5.initialize(path=TERMINAL, timeout=20_000):
        step(f"initialize failed: {mt5.last_error()}")
        return 2
    acc = mt5.account_info()
    term = mt5.terminal_info()
    demo = acc is not None and acc.trade_mode == mt5.ACCOUNT_TRADE_MODE_DEMO
    out: dict = {
        "probed_at": datetime.now(timezone.utc).isoformat(),
        "server": None if acc is None else acc.server,
        "demo_account": demo,
        "terminal_max_bars": None if term is None else term.maxbars,
        "symbols": {},
    }
    step(f"server={out['server']} demo={demo} maxbars={out['terminal_max_bars']}")
    if not demo:
        mt5.shutdown()
        step("not a DEMO account: stop")
        return 3
    names = {s.name for s in (mt5.symbols_get() or [])}
    for sym in SYMBOLS:
        cands = sorted(n for n in names if n.upper().startswith(sym))
        row: dict = {"candidates": cands}
        out["symbols"][sym] = row
        if not cands:
            step(f"{sym}: not offered by this broker")
            continue
        name = sym if sym in cands else cands[0]
        row["broker_symbol"] = name
        step(f"{sym}: select {name}")
        mt5.symbol_select(name, True)
        info = mt5.symbol_info(name)
        if info is not None:
            row["spec"] = {
                k: getattr(info, k)
                for k in (
                    "digits",
                    "point",
                    "spread",
                    "spread_float",
                    "trade_contract_size",
                    "swap_long",
                    "swap_short",
                    "swap_mode",
                    "trade_mode",
                    "currency_base",
                    "currency_profit",
                )
            }
        for tf_name, tf in (("H1", mt5.TIMEFRAME_H1), ("M1", mt5.TIMEFRAME_M1)):
            depth = {}
            for y in WINDOWS:
                a = datetime(y, 3, 3, tzinfo=timezone.utc)
                b = datetime(y, 3, 6, tzinfo=timezone.utc)
                step(f"{sym} {tf_name} range {y}")
                r = mt5.copy_rates_range(name, tf, a, b)
                depth[str(y)] = 0 if r is None else int(len(r))
            row[f"{tf_name}_bars_in_3day_window"] = depth
            step(f"{sym} {tf_name} earliest via from_pos (bounded 200000)")
            r = mt5.copy_rates_from_pos(name, tf, 0, 200_000)
            if r is not None and len(r):
                row[f"{tf_name}_from_pos_200k"] = {
                    "bars": int(len(r)),
                    "first_server_time": datetime.fromtimestamp(
                        int(r[0]["time"]), timezone.utc
                    ).isoformat(),
                    "last_server_time": datetime.fromtimestamp(
                        int(r[-1]["time"]), timezone.utc
                    ).isoformat(),
                }
    mt5.shutdown()
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1, default=str)
    step(f"wrote {OUT}")
    print(json.dumps(out, indent=1, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
