"""Raise the terminal's "Max bars in chart" (common.ini [Charts] MaxBars) - an OWNER tool.

    uv run python scripts/mt5_set_max_bars.py --value 10000000 [--apply]

Dry run by default: prints what would change. With ``--apply`` it edits ONLY the ``MaxBars`` line,
after writing a timestamped backup, and refuses while terminal64.exe is running (the terminal
rewrites common.ini on exit and would undo the change). Start the terminal afterwards, then rerun
``scripts/backfill_mt5.py``. Nothing else in the file (including account fields) is read or printed.
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path


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


def find_common_ini() -> list[Path]:
    base = Path(os.environ.get("APPDATA", "")) / "MetaQuotes" / "Terminal"
    return sorted(base.glob("*/config/common.ini")) if base.is_dir() else []


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--value", type=int, default=10_000_000)
    parser.add_argument("--ini", type=Path, default=None)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    candidates = [args.ini] if args.ini else find_common_ini()
    if len(candidates) != 1:
        print(f"expected exactly one common.ini, found {len(candidates)}; pass --ini")
        return 2
    path = candidates[0]
    raw = path.read_bytes()
    encoding = "utf-16" if raw[:2] in (b"\xff\xfe", b"\xfe\xff") else "utf-8"
    text = raw.decode(encoding)
    match = re.search(r"^MaxBars=(\d+)\s*$", text, flags=re.MULTILINE)
    if match is None:
        print("no MaxBars line under [Charts]; set it in the terminal: Tools > Options > Charts")
        return 2
    print(f"MaxBars: {match.group(1)} -> {args.value}")
    if not args.apply:
        print("dry run (add --apply to write)")
        return 0
    if terminal_running():
        print("refusing: close the MT5 terminal first (it overwrites common.ini on exit)")
        return 3
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    shutil.copy2(path, path.with_name(f"common.ini.bak-{stamp}"))
    updated = text[: match.start()] + f"MaxBars={args.value}" + text[match.end() :]
    path.write_bytes(updated.encode(encoding))
    print("done; start the terminal, then run scripts/backfill_mt5.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
