"""The candidate spec is frozen: its canonical sha256 is recorded, and the evaluation refuses without it."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SPEC = ROOT / "docs" / "research" / "cand_v2_spec.json"
GUARD = SPEC.with_suffix(".sha256")


def canonical_hash(path: Path = SPEC) -> str:
    data = json.loads(path.read_text(encoding="utf-8"))
    text = json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def test_the_spec_matches_its_recorded_hash() -> None:
    assert GUARD.exists(), "the freeze gate: cand_v2_spec.sha256 must be committed with the spec"
    assert GUARD.read_text(encoding="utf-8").strip() == canonical_hash()


def test_the_spec_says_what_the_gate_requires() -> None:
    spec = json.loads(SPEC.read_text(encoding="utf-8"))
    assert spec["status"] == "FROZEN"
    assert spec["windows"]["TEST_H"]["state"].startswith("LOCKED")
    assert spec["windows"]["HOLDOUT"]["state"].startswith("LOCKED")
    assert spec["k_accounting"]["family_ml"]["authority"] == "NONE"
    assert spec["invariants"]["mode"] == "PAPER only"
    assert set(spec["changes"]) >= {"C1", "C2", "C3a", "C3b", "C7"}
    assert spec["changes"]["C7"]["tier"] == "EXPLORATORY"


def test_the_ledger_lists_the_locked_windows_as_unopened() -> None:
    ledger = json.loads(
        (ROOT / "docs" / "research" / "contamination_ledger.json").read_text(encoding="utf-8")
    )
    locked = [e for e in ledger["events"] if "not opened" in e.get("kind", "")]
    assert {e["window"].split()[0] for e in locked} == {"Test-H", "Holdout"}
