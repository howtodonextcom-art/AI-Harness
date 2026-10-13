"""One-off import of V1's broker profile and session exceptions into V2 JSON (read-only on V1).

Run with the V1 interpreter (it has PyYAML):
    <V1>/.venv/Scripts/python.exe scripts/import_v1_config.py

V2 never reads V1 files at run time: the values are copied here with their provenance, and
scripts/parity/check_calendar_clock.py proves they still behave exactly like V1.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import yaml

V1 = Path("Z:/Coding/Projects/AI-Harness/xau-edge/configs/brokers")
OUT = Path(__file__).resolve().parents[1] / "configs"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    profile_path = V1 / "ftmo_demo.yaml"
    exceptions_path = V1 / "ftmo_session_exceptions.yaml"
    profile = yaml.safe_load(profile_path.read_text(encoding="utf-8"))
    exceptions = yaml.safe_load(exceptions_path.read_text(encoding="utf-8"))
    stamp = datetime.now(UTC).isoformat(timespec="seconds")
    cal = profile["validation"]["calendar"]
    out_profile = {
        "provenance": {
            "source": str(profile_path), "sha256": sha(profile_path), "imported_at": stamp,
            "note": "values measured on the FTMO demo terminal 2026-10-08 (V1 report)",
        },
        "name": profile["name"],
        "clock": profile["clock"],
        "instrument": profile["instrument"],
        "calendar": {
            "timezone": cal["timezone"],
            "weekend_close_minute": cal["weekend_close_minute"],
            "weekend_open_minute": cal["weekend_open_minute"],
            "daily_break_start_minute": cal.get("daily_break_start_minute"),
            "daily_break_end_minute": cal.get("daily_break_end_minute"),
        },
    }  # fmt: skip
    closures = [
        {"start": str(c["start"]), "end": str(c["end"]), "reason": c["reason"]}
        for c in exceptions["closures"]
    ]
    out_exceptions = {
        "provenance": {
            "source": str(exceptions_path), "sha256": sha(exceptions_path), "imported_at": stamp,
        },
        "closures": closures,
    }  # fmt: skip
    OUT.mkdir(exist_ok=True)
    (OUT / "ftmo_demo.json").write_text(json.dumps(out_profile, indent=2) + "\n", encoding="utf-8")
    (OUT / "ftmo_session_exceptions.json").write_text(
        json.dumps(out_exceptions) + "\n", encoding="utf-8"
    )
    print(f"profile ok; {len(closures)} closures")


if __name__ == "__main__":
    main()
