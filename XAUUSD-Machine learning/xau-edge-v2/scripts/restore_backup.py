"""Restore data/paper.sqlite3 from a backup file. STOP THE SERVICE FIRST.

    Stop-ScheduledTask XAU-EDGE-V2-Service      (then stop the python process on the port)
    uv run python scripts/restore_backup.py data/backups/paper-YYYYMMDD-HHMMSS.sqlite3 --yes
    Start-ScheduledTask XAU-EDGE-V2-Service

Refuses when the service port still answers, when the backup is not sound, or without --yes.
"""

from __future__ import annotations

import argparse
import socket
import sys
from pathlib import Path

from xau_edge_v2.config import Settings
from xau_edge_v2.paper.restore import RestoreError, restore, verify


def port_open(port: int) -> bool:
    with socket.socket() as s:
        s.settimeout(1)
        return s.connect_ex(("127.0.0.1", port)) == 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("backup", type=Path)
    ap.add_argument("--yes", action="store_true")
    args = ap.parse_args()
    cfg = Settings()
    try:
        counts = verify(args.backup)
    except RestoreError as exc:
        print(f"REFUSED: {exc}")
        return 2
    print(f"backup is sound: {counts}")
    if port_open(cfg.port):
        print(f"REFUSED: something still answers on port {cfg.port}: stop the service first")
        return 3
    if not args.yes:
        print("dry run (add --yes to replace the current database)")
        return 0
    kept, after = restore(args.backup, cfg.paper_db)
    print(f"restored {after}; the previous database was kept as {kept}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
