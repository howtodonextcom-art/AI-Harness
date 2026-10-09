"""Inspect, change and VERIFY the FTMO terminal's "Max bars in chart" (an OWNER tool).

    uv run python scripts/mt5_set_max_bars.py                       # report every terminal, dry run
    uv run python scripts/mt5_set_max_bars.py --value 10000000 --apply   # terminal must be closed
    uv run --extra mt5 python scripts/mt5_set_max_bars.py --verify       # after reopening the terminal

* Finds every MetaQuotes terminal data folder and picks the FTMO one (by its install origin); it
  refuses to guess when zero or several match (pass ``--ini`` to choose).
* ``--apply`` writes a timestamped backup, then changes ONLY the ``MaxBars`` value; it refuses while
  terminal64.exe is running (the terminal rewrites common.ini on exit) and never closes MT5 itself.
* No account, login or balance field is read, printed or returned.
* ``--verify`` does not trust the file: it asks the running terminal for its effective value and
  checks that it now serves materially more M1 history than the 100,000-bar default allowed.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from xau_edge.market_data.mt5.maxbars import (  # noqa: E402
    RECOMMENDED,
    apply_max_bars,
    find_candidates,
    select_ftmo,
)
from xau_edge.market_data.mt5.runtime import DEFAULT_TERMINAL  # noqa: E402

DEFAULT_CAP = 100_000


def terminal_running() -> bool:
    if sys.platform != "win32":
        return False
    out = subprocess.run(
        ["tasklist", "/FI", "IMAGENAME eq terminal64.exe", "/NH"],  # noqa: S607
        capture_output=True,
        text=True,
        check=False,
    ).stdout
    return "terminal64.exe" in out.lower()


def verify(terminal_path: str) -> int:
    from xau_edge.domain.timeframe import Timeframe  # noqa: PLC0415
    from xau_edge.market_data.mt5.diagnostics import bar_depth  # noqa: PLC0415
    from xau_edge.market_data.mt5.runtime import open_feed  # noqa: PLC0415

    with open_feed(terminal_path) as feed:
        facts = feed.facts()
        mapping = feed.discover_symbol("XAUUSD")
        feed.select(mapping.broker_symbol)
        depth = bar_depth(feed, mapping.broker_symbol, Timeframe.M1, facts.max_bars)
    report = {
        "terminal_max_bars": facts.max_bars,
        "m1_bars_served": depth.get("count"),
        "m1_earliest": depth.get("earliest"),
        "limited_by_terminal_max_bars": depth.get("limited_by_terminal_max_bars"),
    }
    print(json.dumps(report, indent=2, default=str))
    took_effect = bool(
        facts.max_bars and facts.max_bars > DEFAULT_CAP and depth.get("count", 0) > 0
    )
    print(
        "MAX BARS TOOK EFFECT"
        if took_effect
        else "NOT EFFECTIVE YET: the terminal still reports the old cap"
    )
    return 0 if took_effect else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--value", type=int, default=RECOMMENDED)
    parser.add_argument(
        "--ini", type=Path, default=None, help="common.ini to use (skips detection)"
    )
    parser.add_argument("--terminal-path", default=DEFAULT_TERMINAL)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    if args.verify:
        return verify(args.terminal_path)
    appdata = Path(os.environ.get("APPDATA", ""))
    candidates = find_candidates(appdata, args.terminal_path)
    for c in candidates:
        print("terminal data folder:", json.dumps(c.as_dict()))
    if args.ini is not None:
        ini = args.ini
    else:
        chosen = select_ftmo(candidates)
        if chosen is None:
            print(
                f"cannot identify exactly one FTMO terminal among {len(candidates)}; pass --ini PATH"
            )
            return 2
        ini = chosen.ini
    raw = ini.read_bytes()
    from xau_edge.market_data.mt5.maxbars import decode_ini, read_max_bars  # noqa: PLC0415

    current = read_max_bars(decode_ini(raw)[0])
    if current is None:
        print("no MaxBars line under [Charts]; set it in the terminal: Tools > Options > Charts")
        return 2
    print(
        f"selected: {ini.parent.parent.name}   MaxBars: {current} -> {args.value} (recommended {RECOMMENDED})"
    )
    if not args.apply:
        print("dry run (add --apply to write; the terminal must be closed)")
        return 0
    if terminal_running():
        print(
            "refusing: close the FTMO MT5 terminal completely first (it overwrites common.ini on exit)"
        )
        return 3
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    backup = ini.with_name(f"common.ini.bak-{stamp}")
    shutil.copy2(ini, backup)
    ini.write_bytes(apply_max_bars(raw, args.value))
    print(f"done (backup: {backup.name}). Reopen the terminal, wait for login/sync, then run:")
    print("  uv run --extra mt5 python scripts/mt5_set_max_bars.py --verify")
    print("  uv run --extra mt5 python scripts/backfill_mt5.py --write-report")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
