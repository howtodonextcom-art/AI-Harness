"""Live dry-run soak: poll ``GET /trade/decision`` and check the desk behaves like a trading tool.

Read-only (GET only, no order of any kind). It records latency, errors, decision flicker (a decision
that changes while no new closed M1 bar arrived), expired or stale plans served as actionable, and
the mix of decisions, then writes a JSON report.

Usage: ``uv run python scripts/trade_soak.py --minutes 30 [--url http://127.0.0.1:8000]``
"""

from __future__ import annotations

import argparse
import json
import statistics
import time
import urllib.request
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

POLL_SECONDS = 5.0


def fetch(url: str) -> tuple[dict[str, Any] | None, float, str | None]:
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(url, timeout=10) as res:  # noqa: S310 - fixed local URL
            body = json.loads(res.read())
        return body, (time.perf_counter() - started) * 1000, None
    except Exception as exc:
        return None, (time.perf_counter() - started) * 1000, type(exc).__name__


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--minutes", type=float, default=30.0)
    parser.add_argument("--url", default="http://127.0.0.1:8000")
    parser.add_argument("--out", default="data/trade/reports/soak.json")
    args = parser.parse_args()
    deadline = time.monotonic() + args.minutes * 60
    latencies: list[float] = []
    errors: Counter[str] = Counter()
    decisions: Counter[str] = Counter()
    flicker: list[dict[str, Any]] = []
    violations: Counter[str] = Counter()
    setups: set[str] = set()
    polls = 0
    last: dict[str, Any] | None = None
    first_at = datetime.now(UTC)
    while time.monotonic() < deadline:
        body, ms, err = fetch(f"{args.url}/trade/decision")
        polls += 1
        latencies.append(ms)
        if body is None or err:
            errors[err or "EMPTY"] += 1
        elif not body.get("available"):
            errors["NOT_AVAILABLE"] += 1
        else:
            d = body["decision"]
            decisions[d["decision"]] += 1
            if d["setup_id"] and d["decision"] != "WAIT":
                setups.add(d["setup_id"])
            if body.get("engine_errors"):
                errors["ENGINE_ERROR"] += 1
            if body["actionable"] and (d["expired"] or (body["data_age_seconds"] or 0) > 120):
                violations["ACTIONABLE_BUT_EXPIRED_OR_STALE"] += 1
            if body["actionable"] and body["quote"] and body["quote"]["stale"]:
                violations["ACTIONABLE_WITH_STALE_QUOTE"] += 1
            if d["decision"] == "WAIT" and not d["refusal_reasons"]:
                violations["WAIT_WITHOUT_REASON"] += 1
            if body["demo"]["paper_desk_sends_orders"] is not False:
                violations["DEMO_LOCK_CLAIM_WRONG"] += 1
            if last is not None and last["data_as_of"] == body["data_as_of"]:
                a, b = last["decision"], d
                if (a["decision"], a["setup_id"]) != (b["decision"], b["setup_id"]):
                    flicker.append(
                        {"at": body["served_at"], "from": a["decision"], "to": b["decision"]}
                    )
            last = {"data_as_of": body["data_as_of"], "decision": d}
        time.sleep(POLL_SECONDS)
    ordered = sorted(latencies)
    report = {
        "started": first_at.isoformat(),
        "minutes": args.minutes,
        "polls": polls,
        "errors": dict(errors),
        "decisions": dict(decisions),
        "distinct_actionable_setups": len(setups),
        "flicker_events": len(flicker),
        "flicker_examples": flicker[:5],
        "violations": dict(violations),
        "latency_ms": {
            "median": round(statistics.median(latencies), 1),
            "p95": round(ordered[int(0.95 * (len(ordered) - 1))], 1),
            "max": round(max(latencies), 1),
        },
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
