"""Read-only sampler of the FTMO terminal's current tick (symbol_info_tick), for the latency audit.

Attaches to the collector's own terminal read-only (no order function, no account information, no setting).
Run it with V1's interpreter, at the same time as p0_measure.py.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import MetaTrader5 as mt5  # noqa: N813

FTMO = r"C:\Program Files\FTMO Global Markets MT5 Terminal\terminal64.exe"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seconds", type=float, default=70)
    ap.add_argument("--hz", type=float, default=10)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    if not mt5.initialize(path=FTMO):
        raise SystemExit(mt5.last_error())
    rows = []
    t_end = time.time() + a.seconds
    while time.time() < t_end:
        t0 = time.time()
        k = mt5.symbol_info_tick("XAUUSD")
        if k is not None:
            rows.append(
                {"t": t0, "bid": float(k.bid), "ask": float(k.ask), "tick_ms": int(k.time_msc)}
            )
        time.sleep(max(0.0, 1 / a.hz - (time.time() - t0)))
    mt5.shutdown()
    Path(a.out).write_text(json.dumps(rows), encoding="utf-8")
    print(len(rows), "samples")


if __name__ == "__main__":
    main()
