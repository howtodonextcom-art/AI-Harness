"""A1 probe: does a FRESH FTMO terminal (empty local cache) serve the daily pseudo-bar?

Read-only: ``copy_rates_range`` only (no order function, no account information). Refuses to attach to the
terminals of the collector or of the default MetaQuotes install: it must be the separate portable copy.
Run it with an interpreter that has ``MetaTrader5`` (V1's venv), after the manual steps in a1_launch_portable.ps1.

    <V1>/.venv/Scripts/python.exe scripts/research/a1_probe.py --terminal D:/XAU-EDGE-V2-A1/ftmo-portable/terminal64.exe

Interpretation (written to the output):
  pseudo-bars present in the fresh terminal  -> FTMO SERVER history contains them (not a local cache artefact);
  absent                                     -> an artefact of the long-running terminal's local cache.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import MetaTrader5 as mt5  # noqa: N813

FORBIDDEN = (r"c:\program files\ftmo global markets mt5 terminal", r"c:\program files\metatrader 5")
WEEKS = {"2013-05": (datetime(2013, 5, 13, tzinfo=UTC), datetime(2013, 5, 17, tzinfo=UTC)),
         "2016-05": (datetime(2016, 5, 9, tzinfo=UTC), datetime(2016, 5, 13, tzinfo=UTC)),
         "2019-05": (datetime(2019, 5, 13, tzinfo=UTC), datetime(2019, 5, 17, tzinfo=UTC)),
         "2020-12": (datetime(2020, 12, 14, tzinfo=UTC), datetime(2020, 12, 18, tzinfo=UTC))}  # fmt: skip


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--terminal", required=True)
    ap.add_argument("--out", default="a1_probe_result.json")
    a = ap.parse_args()
    exe = str(Path(a.terminal)).lower()
    if any(exe.startswith(f) for f in FORBIDDEN) or "portable" not in exe:
        sys.exit(
            "refusing: the probe must attach to the separate portable copy, never to the collector's terminal"
        )
    if not mt5.initialize(path=a.terminal, portable=True):
        sys.exit(f"cannot attach: {mt5.last_error()}")
    info = mt5.terminal_info()._asdict()
    result: dict[str, object] = {
        "terminal": {k: info[k] for k in ("company", "path", "maxbars", "connected")},
        "weeks": {},
    }
    if not info["connected"] or info["maxbars"] < 5_000_000:
        mt5.shutdown()
        sys.exit(
            f"not ready: connected={info['connected']} maxbars={info['maxbars']} (log in, set Max bars to Unlimited, restart)"
        )
    verdict = {}
    for lab, (s, e) in WEEKS.items():
        rows = mt5.copy_rates_range("XAUUSD", mt5.TIMEFRAME_M1, s, e)
        n = 0 if rows is None else len(rows)
        pseudo = (
            0
            if rows is None
            else sum(
                1
                for r in rows
                if int(r["spread"]) == 0
                and int(r["tick_volume"]) >= 20_000
                and int(r["time"]) % 3600 == 0
            )
        )
        result["weeks"][lab] = {"m1_bars": n, "pseudo_like": pseudo}  # type: ignore[index]
        verdict[lab] = pseudo
    mt5.shutdown()
    present = any(v > 0 for v in verdict.values())
    result["interpretation"] = (
        "PSEUDO-BARS PRESENT in a fresh terminal: the FTMO server history contains them"
        if present
        else "ABSENT in a fresh terminal: the pseudo-bars are an artefact of the old terminal's local cache"
    )
    Path(a.out).write_text(json.dumps(result, indent=1), encoding="utf-8")
    print(json.dumps(result, indent=1))


if __name__ == "__main__":
    main()
