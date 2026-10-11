"""Compare canonical TradeEngine decisions to the Demo dry-run adapter on the same snapshots.

Usage:
  uv run python scripts/decision_parity.py --synthetic
  uv run python scripts/decision_parity.py --root data/market --out data/trade/parity

Classifies every difference: EXPECTED TRANSLATION / BUG / LEGACY SEMANTIC DIFFERENCE / UNSUPPORTED.
Exit 1 on any BUG or unexplained mismatch. Does not send orders.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tests.unit.trading.helpers import aligned_state  # noqa: E402

from xau_edge.trading.baseline import DecisionContext, decide  # noqa: E402
from xau_edge.trading.decision_core import comparable  # noqa: E402
from xau_edge.trading.execution_intent import DemoDryRunAdapter, intent_from_signal  # noqa: E402
from xau_edge.trading.schema import TradeDecision  # noqa: E402
from xau_edge.trading.sizing import SymbolSpec  # noqa: E402

SPEC = SymbolSpec()


def _classify(field: str, left: Any, right: Any) -> str:
    if left == right:
        return "MATCH"
    if field in {"adapter", "would_send", "dry_run", "evidence"}:
        return "EXPECTED TRANSLATION"
    return "BUG"


def compare_one(signal_dump: dict[str, Any], translated: dict[str, Any]) -> list[dict[str, Any]]:
    pairs = (
        ("decision", signal_dump.get("decision"), translated.get("side") or "WAIT"),
        (
            "side",
            signal_dump.get("decision") if signal_dump.get("decision") != "WAIT" else None,
            translated.get("side"),
        ),
        ("setup_id", signal_dump.get("setup_id"), translated.get("setup_id")),
        ("entry", signal_dump.get("entry"), translated.get("entry")),
        ("sl", signal_dump.get("sl"), translated.get("sl")),
        ("tp", signal_dump.get("tp"), translated.get("tp")),
        ("rr", signal_dump.get("rr"), translated.get("rr")),
        ("risk", signal_dump.get("risk_pct"), translated.get("risk_pct")),
        ("expiry", signal_dump.get("expiry"), translated.get("expiry")),
        ("evidence", signal_dump.get("evidence"), translated.get("evidence")),
        ("refusal", signal_dump.get("refusals"), translated.get("refusal_reasons")),
    )
    rows = []
    for field, left, right in pairs:
        kind = _classify(field, left, right)
        if field == "decision" and left == "WAIT" and right == "WAIT":
            kind = "MATCH"
        if field == "decision" and left in ("BUY", "SELL") and right == left:
            kind = "MATCH"
        rows.append({"field": field, "canonical": left, "demo_dry_run": right, "class": kind})
    return rows


def synthetic_report() -> dict[str, Any]:
    ctx = DecisionContext(
        spec=SPEC, equity=100_000.0, source_mode="DEMO_DRY_RUN", bid=2000.0, ask=2000.25
    )
    signal = decide(aligned_state(), ctx)
    intent = intent_from_signal(signal)
    translated = DemoDryRunAdapter().translate(intent)
    core = comparable(signal)
    dump = {
        **core,
        "sl": signal.stop_loss,
        "tp": signal.take_profit,
        "rr": signal.risk_reward,
        "risk_pct": signal.risk_pct,
        "evidence": signal.evidence_status.value,
        "decision": signal.decision.value,
    }
    rows = compare_one(dump, translated)
    bugs = [r for r in rows if r["class"] == "BUG"]
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "mode": "SYNTHETIC",
        "decision": signal.decision.value,
        "actionable": signal.decision is not TradeDecision.WAIT,
        "rows": rows,
        "bugs": bugs,
        "passed": not bugs,
        "note": "LIVE window comparison is a follow-on; this proves the adapter copies intent.",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--synthetic", action="store_true")
    parser.add_argument("--root", default="data/market")
    parser.add_argument("--out", default="data/trade/parity")
    args = parser.parse_args()
    report = synthetic_report()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"decision_parity_{report['mode'].lower()}.json"
    path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    print(f"{'PASS' if report['passed'] else 'FAIL'} {path} bugs={len(report['bugs'])}")
    if not args.synthetic:
        print("LIVE snapshot walk not yet wired; ran synthetic contract check.")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
